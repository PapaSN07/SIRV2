"""Tests d'intégration — failles de droits restantes après le correctif des comptes à plusieurs rôles.

A. Un admin non superadmin ne modifie pas ses propres rôles et ne réinitialise pas son propre
   mot de passe par l'administration (son profil reste modifiable).
B. Un rôle créé dans la matrice (hors ROLES_SYSTEME) relève d'une direction selon ses droits :
   direction D si toutes les ressources de ses droits sont dans propres(D) ∪ partagées ; un rôle
   sans droit relève des deux ; un rôle portant une ressource réservée (admin_roles,
   admin_utilisateurs) ne relève d'aucune. Un admin de direction n'attribue que les rôles créés de
   sa direction et n'agit que sur les comptes dont chaque rôle créé relève de sa direction.
C. Un rôle désactivé ne donne aucun droit (`require_permission`, `require_role`).
D. Un compte désactivé est refusé même avec un jeton valide (garde, déjà en place).

Refus = 403 enveloppé {"status": "error", "data": None, "error": "..."}, sans écriture ni audit.
Objets ORM en mémoire, repositories mockés : aucune base réelle.
"""

import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, Response

from app.core.deps import require_permission, require_role
from app.core.security import create_access_token
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.repositories import admin_utilisateur_repository as admin_repo
from app.schemas.base_clients import DroitsAtelier

pytestmark = pytest.mark.asyncio

URL = "/api/v1/admin/utilisateurs"
URL_DROITS_ATELIER = "/api/v1/clients/atelier/droits"  # protégée par require_permission("indicateurs", "read")
NOUVEAU_MDP = {"new_password": "NouveauMotDePasse1!"}

# ---------------------------------------------------------------------------
# Catalogue des rôles : rôles SIRV2 et rôles créés dans la matrice (avec leurs droits)
# ---------------------------------------------------------------------------

_DROITS_ADMIN = [
    ("admin_utilisateurs", "read"),
    ("admin_utilisateurs", "create"),
    ("admin_utilisateurs", "update"),
]

# nom → (id, droits)
CATALOGUE: dict[str, tuple[int, list[tuple[str, str]]]] = {
    "ADMIN_SCR": (1, _DROITS_ADMIN),
    "ADMIN_DISPATCHING": (2, _DROITS_ADMIN),
    "SUPERADMIN": (3, []),
    "BCC": (10, []),
    "BRC": (11, []),
    "SUPERVISEUR": (12, []),
    "DISPATCHER": (13, []),
    "ADMIN_SAQS": (14, []),
    # Rôles créés (hors ROLES_SYSTEME)
    "CREE_SANS_DROIT": (50, []),
    "CREE_TRANSPORT_VALIDATE": (51, [("interruptions_transport", "validate")]),
    "CREE_ADMIN_ROLES_UPDATE": (52, [("admin_roles", "update")]),
    "CREE_DISTRIB_READ": (53, [("interruptions_distribution", "read")]),
    "CREE_INDIC_RAPPORTS": (54, [("indicateurs", "read"), ("rapports", "read")]),
    "CREE_RAPPORTS": (55, [("rapports", "read")]),
    "CREE_DISTRIB_UPDATE": (56, [("interruptions_distribution", "update")]),
    "CREE_TRANSPORT_READ": (57, [("interruptions_transport", "read")]),
    "CREE_ADMIN_ROLES_READ": (58, [("admin_roles", "read")]),
    "CREE_INDICATEURS": (59, [("indicateurs", "read")]),
}

_ROLES_AVEC_SCOPE = {"BCC", "BRC", "SUPERVISEUR"}
_PERMISSION_IDS: dict[tuple[str, str], int] = {}


def _rid(nom: str) -> int:
    return CATALOGUE[nom][0]


def _permission(ressource: str, action: str) -> Permission:
    pid = _PERMISSION_IDS.setdefault((ressource, action), len(_PERMISSION_IDS) + 1)
    perm = Permission()
    perm.id = pid
    perm.ressource = ressource
    perm.action = action
    perm.description = f"{ressource}:{action}"
    return perm


def _role(nom: str, actif: bool = True) -> Role:
    rid, droits = CATALOGUE[nom]
    role = Role()
    role.id = rid
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = actif
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(droits, start=1):
        perm = _permission(ressource, action)
        rp = RolePermission()
        rp.id = rid * 100 + i
        rp.role_id = rid
        rp.permission_id = perm.id
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps
    return role


def _utilisateur(
    user_id: int,
    login: str,
    roles: list[str],
    inactifs: frozenset[str] = frozenset(),
    compte_actif: bool = True,
) -> Utilisateur:
    """Utilisateur portant les rôles donnés (scope 1 pour BCC / BRC / SUPERVISEUR)."""
    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = "hash-non-utilise"
    user.nom = "Nom"
    user.prenom = "Prenom"
    user.email = f"{login}@senelec.sn"
    user.telephone = None
    user.matricule = None
    user.is_active = compte_actif
    user.premiere_connexion = False
    user.audit_logs = []
    user_roles: list[UserRole] = []
    for i, nom in enumerate(roles, start=1):
        ur = UserRole()
        ur.id = user_id * 10 + i
        ur.utilisateur_id = user_id
        ur.role_id = _rid(nom)
        ur.scope_service_id = 1 if nom in _ROLES_AVEC_SCOPE else None
        ur.role = _role(nom, actif=nom not in inactifs)
        ur.utilisateur = user
        user_roles.append(ur)
    user.user_roles = user_roles
    return user


def _admin_scr() -> Utilisateur:
    return _utilisateur(1, "admin_scr", ["ADMIN_SCR"])


def _admin_dispatching() -> Utilisateur:
    return _utilisateur(2, "admin_dispatch", ["ADMIN_DISPATCHING"])


def _superadmin() -> Utilisateur:
    return _utilisateur(3, "superadmin", ["SUPERADMIN"])


def _cible(roles: list[str], user_id: int = 100) -> Utilisateur:
    return _utilisateur(user_id, f"cible_{user_id}", roles)


def _token(user: Utilisateur) -> dict[str, str]:
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom if user.user_roles else "AUCUN"},
    )
    return {"Authorization": f"Bearer {token}"}


def _attribution(nom: str) -> dict:
    return {"role_id": _rid(nom), "scope_service_id": 1 if nom in _ROLES_AVEC_SCOPE else None}


# ---------------------------------------------------------------------------
# Mocks des repositories
# ---------------------------------------------------------------------------


@dataclass
class Ecritures:
    reset_password: AsyncMock
    set_active: AsyncMock
    update_profile: AsyncMock
    replace_roles: AsyncMock
    create: AsyncMock
    log_audit: AsyncMock

    def verifier_aucune_ecriture(self) -> None:
        self.reset_password.assert_not_awaited()
        self.set_active.assert_not_awaited()
        self.update_profile.assert_not_awaited()
        self.replace_roles.assert_not_awaited()
        self.create.assert_not_awaited()
        self.log_audit.assert_not_awaited()


@contextmanager
def _environnement(acteur: Utilisateur, cible: Utilisateur | None = None) -> Iterator[Ecritures]:
    """Utilisateur connecté = acteur ; cible chargée par le repository admin (droits des rôles inclus)."""
    cible = cible if cible is not None else acteur

    async def _get_utilisateur(db, uid):  # noqa: ANN001, ANN202
        return acteur if uid == acteur.id else cible

    async def _get_role(db, role_id):  # noqa: ANN001, ANN202
        for nom, (rid, _) in CATALOGUE.items():
            if rid == role_id:
                return _role(nom)
        return None

    async def _update_profile(db, user, **kwargs):  # noqa: ANN001, ANN003, ANN202
        return user

    async def _set_active(db, user_id, is_active):  # noqa: ANN001, ANN202
        cible.is_active = is_active
        return cible

    async def _create(db, *, login, roles, **kwargs):  # noqa: ANN001, ANN003, ANN202
        noms = {rid: nom for nom, (rid, _) in CATALOGUE.items()}
        return _utilisateur(500, login, [noms[rid] for rid, _ in roles])

    with ExitStack() as pile:
        pile.enter_context(
            patch("app.repositories.utilisateur_repository.get_by_id", side_effect=_get_utilisateur)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_by_id", new_callable=AsyncMock, return_value=cible)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_by_login", new_callable=AsyncMock, return_value=None)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_role_by_id", side_effect=_get_role)
        )
        ecritures = Ecritures(
            reset_password=pile.enter_context(
                patch("app.repositories.admin_utilisateur_repository.reset_password", new_callable=AsyncMock)
            ),
            set_active=pile.enter_context(
                patch(
                    "app.repositories.admin_utilisateur_repository.set_active",
                    new_callable=AsyncMock,
                    side_effect=_set_active,
                )
            ),
            update_profile=pile.enter_context(
                patch(
                    "app.repositories.admin_utilisateur_repository.update_profile",
                    new_callable=AsyncMock,
                    side_effect=_update_profile,
                )
            ),
            replace_roles=pile.enter_context(
                patch("app.repositories.admin_utilisateur_repository.replace_roles", new_callable=AsyncMock)
            ),
            create=pile.enter_context(
                patch(
                    "app.repositories.admin_utilisateur_repository.create",
                    new_callable=AsyncMock,
                    side_effect=_create,
                )
            ),
            log_audit=pile.enter_context(
                patch("app.services.admin_utilisateur_service.log_audit", new_callable=AsyncMock)
            ),
        )
        yield ecritures


def _verifier_refus(response: Response, ecritures: Ecritures | None = None) -> None:
    assert response.status_code == 403, f"Attendu 403, obtenu {response.status_code} : {response.text}"
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["data"] is None
    assert isinstance(detail["error"], str) and detail["error"].strip()
    if ecritures is not None:
        ecritures.verifier_aucune_ecriture()


async def _put(client: AsyncClient, acteur: Utilisateur, cible: Utilisateur, body: dict) -> tuple[Response, Ecritures]:
    with _environnement(acteur, cible) as ecritures:
        response = await client.put(f"{URL}/{cible.id}", headers=_token(acteur), json=body)
    return response, ecritures


async def _reset(client: AsyncClient, acteur: Utilisateur, cible: Utilisateur) -> tuple[Response, Ecritures]:
    with _environnement(acteur, cible) as ecritures:
        response = await client.post(f"{URL}/{cible.id}/reset-password", headers=_token(acteur), json=NOUVEAU_MDP)
    return response, ecritures


async def _creer(client: AsyncClient, acteur: Utilisateur, roles: list[str]) -> tuple[Response, Ecritures]:
    body = {
        "login": "nouveau_compte",
        "password": "MotDePasse123!",
        "nom": "Nouveau",
        "prenom": "Compte",
        "roles": [_attribution(nom) for nom in roles],
    }
    with _environnement(acteur) as ecritures:
        response = await client.post(URL, headers=_token(acteur), json=body)
    return response, ecritures


# ===========================================================================
# A. Un admin sur son propre compte
# ===========================================================================


async def test_admin_scr_ne_s_ajoute_pas_un_role_cree(client: AsyncClient) -> None:
    acteur = _admin_scr()
    response, ecritures = await _put(
        client, acteur, acteur, {"roles": [_attribution("ADMIN_SCR"), _attribution("CREE_SANS_DROIT")]}
    )
    _verifier_refus(response, ecritures)


async def test_admin_scr_ne_se_retire_pas_admin_scr(client: AsyncClient) -> None:
    acteur = _admin_scr()
    response, ecritures = await _put(client, acteur, acteur, {"roles": [_attribution("BCC")]})
    _verifier_refus(response, ecritures)


async def test_admin_scr_ne_reinitialise_pas_son_propre_mot_de_passe(client: AsyncClient) -> None:
    acteur = _admin_scr()
    response, ecritures = await _reset(client, acteur, acteur)
    _verifier_refus(response, ecritures)


async def test_admin_dispatching_ne_reinitialise_pas_son_propre_mot_de_passe(client: AsyncClient) -> None:
    acteur = _admin_dispatching()
    response, ecritures = await _reset(client, acteur, acteur)
    _verifier_refus(response, ecritures)


# Gardes vertes


async def test_admin_scr_modifie_son_propre_profil(client: AsyncClient) -> None:
    acteur = _admin_scr()
    response, ecritures = await _put(client, acteur, acteur, {"nom": "Nouveau nom"})
    assert response.status_code == 200, response.text
    ecritures.update_profile.assert_awaited_once()
    ecritures.replace_roles.assert_not_awaited()


async def test_admin_scr_renvoie_ses_roles_identiques(client: AsyncClient) -> None:
    acteur = _admin_scr()
    response, _ = await _put(client, acteur, acteur, {"nom": "Nom", "roles": [_attribution("ADMIN_SCR")]})
    assert response.status_code == 200, response.text


async def test_superadmin_reinitialise_son_propre_mot_de_passe(client: AsyncClient) -> None:
    acteur = _superadmin()
    response, ecritures = await _reset(client, acteur, acteur)
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


# ===========================================================================
# B. Rôles créés et directions — attribution
# ===========================================================================

_CAS_ATTRIBUTION_REFUSEE = [
    pytest.param("ADMIN_SCR", "BCC", "CREE_TRANSPORT_VALIDATE", id="admin_scr_role_cree_transport_validate"),
    pytest.param("ADMIN_DISPATCHING", "DISPATCHER", "CREE_ADMIN_ROLES_UPDATE", id="admin_dispatching_role_cree_admin_roles"),
    pytest.param("ADMIN_DISPATCHING", "DISPATCHER", "CREE_DISTRIB_READ", id="admin_dispatching_role_cree_distribution_read"),
]

_CAS_ATTRIBUTION_ACCEPTEE = [
    pytest.param("ADMIN_SCR", "BCC", "CREE_INDIC_RAPPORTS", id="admin_scr_role_cree_indicateurs_rapports"),
    pytest.param("ADMIN_DISPATCHING", "DISPATCHER", "CREE_RAPPORTS", id="admin_dispatching_role_cree_rapports"),
    pytest.param("SUPERADMIN", "BCC", "CREE_TRANSPORT_VALIDATE", id="superadmin_role_cree_transport_validate"),
]

_ACTEURS = {"ADMIN_SCR": _admin_scr, "ADMIN_DISPATCHING": _admin_dispatching, "SUPERADMIN": _superadmin}


@pytest.mark.parametrize(("acteur_nom", "role_base", "role_cree"), _CAS_ATTRIBUTION_REFUSEE)
async def test_modification_refuse_un_role_cree_hors_direction(
    client: AsyncClient, acteur_nom: str, role_base: str, role_cree: str
) -> None:
    response, ecritures = await _put(
        client,
        _ACTEURS[acteur_nom](),
        _cible([role_base]),
        {"roles": [_attribution(role_base), _attribution(role_cree)]},
    )
    _verifier_refus(response, ecritures)


@pytest.mark.parametrize(("acteur_nom", "role_base", "role_cree"), _CAS_ATTRIBUTION_REFUSEE)
async def test_creation_refuse_un_role_cree_hors_direction(
    client: AsyncClient, acteur_nom: str, role_base: str, role_cree: str
) -> None:
    response, ecritures = await _creer(client, _ACTEURS[acteur_nom](), [role_base, role_cree])
    _verifier_refus(response, ecritures)


@pytest.mark.parametrize(("acteur_nom", "role_base", "role_cree"), _CAS_ATTRIBUTION_ACCEPTEE)
async def test_modification_accepte_un_role_cree_de_la_direction(
    client: AsyncClient, acteur_nom: str, role_base: str, role_cree: str
) -> None:
    response, ecritures = await _put(
        client,
        _ACTEURS[acteur_nom](),
        _cible([role_base]),
        {"roles": [_attribution(role_base), _attribution(role_cree)]},
    )
    assert response.status_code == 200, response.text
    ecritures.replace_roles.assert_awaited_once()


@pytest.mark.parametrize(("acteur_nom", "role_base", "role_cree"), _CAS_ATTRIBUTION_ACCEPTEE)
async def test_creation_accepte_un_role_cree_de_la_direction(
    client: AsyncClient, acteur_nom: str, role_base: str, role_cree: str
) -> None:
    response, ecritures = await _creer(client, _ACTEURS[acteur_nom](), [role_base, role_cree])
    assert response.status_code == 201, response.text
    ecritures.create.assert_awaited_once()
    ecritures.log_audit.assert_awaited_once()


# ===========================================================================
# B. Rôles créés et directions — périmètre sur une cible existante
# ===========================================================================


async def test_admin_dispatching_ne_reinitialise_pas_le_mdp_d_un_compte_a_role_cree_distribution(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _admin_dispatching(), _cible(["CREE_DISTRIB_UPDATE"]))
    _verifier_refus(response, ecritures)


async def test_admin_scr_ne_desactive_pas_un_bcc_portant_un_role_cree_transport(client: AsyncClient) -> None:
    acteur, cible = _admin_scr(), _cible(["BCC", "CREE_TRANSPORT_READ"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.patch(f"{URL}/{cible.id}/desactiver", headers=_token(acteur))
    _verifier_refus(response, ecritures)


async def test_admin_scr_reinitialise_le_mdp_d_un_bcc_portant_un_role_cree_rapports(client: AsyncClient) -> None:
    """Garde : rôle créé à ressource partagée → dans le périmètre distribution."""
    response, ecritures = await _reset(client, _admin_scr(), _cible(["BCC", "CREE_RAPPORTS"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


@pytest.mark.parametrize(
    ("roles", "direction", "attendu"),
    [
        # Rouges
        pytest.param(["CREE_DISTRIB_UPDATE"], "transport", False, id="role_cree_distribution_en_transport"),
        pytest.param(["BCC", "CREE_TRANSPORT_READ"], "distribution", False, id="bcc_role_cree_transport_en_distribution"),
        pytest.param(["CREE_ADMIN_ROLES_READ"], "distribution", False, id="role_cree_admin_roles_en_distribution"),
        pytest.param(["CREE_ADMIN_ROLES_READ"], "transport", False, id="role_cree_admin_roles_en_transport"),
        # Gardes
        pytest.param(["CREE_SANS_DROIT"], "distribution", True, id="role_cree_sans_droit_en_distribution"),
        pytest.param(["CREE_SANS_DROIT"], "transport", True, id="role_cree_sans_droit_en_transport"),
        pytest.param(["BCC", "CREE_RAPPORTS"], "distribution", True, id="bcc_role_cree_rapports_en_distribution"),
        pytest.param(["CREE_DISTRIB_UPDATE"], "distribution", True, id="role_cree_distribution_en_distribution"),
        pytest.param(["DISPATCHER", "CREE_TRANSPORT_READ"], "transport", True, id="dispatcher_role_cree_transport_en_transport"),
    ],
)
async def test_user_has_direction_role_tient_compte_des_droits_des_roles_crees(
    roles: list[str], direction: str, attendu: bool
) -> None:
    assert admin_repo.user_has_direction_role(_cible(roles), direction) is attendu


# ===========================================================================
# C. Rôles désactivés : aucun droit
# ===========================================================================


@contextmanager
def _route_droits_atelier(utilisateur: Utilisateur) -> Iterator[AsyncMock]:
    droits = DroitsAtelier(peut_proposer=False, peut_valider=False, periode=None)
    with (
        patch("app.repositories.utilisateur_repository.get_by_id", new_callable=AsyncMock, return_value=utilisateur),
        patch(
            "app.services.atelier_clients_service.get_droits", new_callable=AsyncMock, return_value=droits
        ) as service,
    ):
        yield service


async def test_require_permission_ignore_un_role_cree_desactive(client: AsyncClient) -> None:
    compte = _utilisateur(200, "lecteur", ["CREE_INDICATEURS"], inactifs=frozenset({"CREE_INDICATEURS"}))
    with _route_droits_atelier(compte) as service:
        response = await client.get(URL_DROITS_ATELIER, headers=_token(compte))
    _verifier_refus(response)
    service.assert_not_awaited()


async def test_require_permission_accepte_le_meme_role_actif(client: AsyncClient) -> None:
    compte = _utilisateur(200, "lecteur", ["CREE_INDICATEURS"])
    with _route_droits_atelier(compte) as service:
        response = await client.get(URL_DROITS_ATELIER, headers=_token(compte))
    assert response.status_code == 200, response.text
    service.assert_awaited_once()


async def test_require_permission_ignore_le_role_desactive_meme_avec_un_autre_role_actif() -> None:
    """BCC actif sans indicateurs:read + rôle créé désactivé portant indicateurs:read → 403."""
    compte = _utilisateur(201, "bcc_lecteur", ["BCC", "CREE_INDICATEURS"], inactifs=frozenset({"CREE_INDICATEURS"}))
    with pytest.raises(HTTPException) as exc:
        await require_permission("indicateurs", "read")(current_user=compte)
    assert exc.value.status_code == 403
    assert exc.value.detail["status"] == "error" and exc.value.detail["data"] is None


async def test_require_role_ignore_un_role_desactive() -> None:
    compte = _utilisateur(202, "ancien_admin", ["ADMIN_SCR"], inactifs=frozenset({"ADMIN_SCR"}))
    with pytest.raises(HTTPException) as exc:
        await require_role("ADMIN_SCR", "ADMIN_DISPATCHING")(current_user=compte)
    assert exc.value.status_code == 403
    assert exc.value.detail["status"] == "error" and exc.value.detail["data"] is None
    assert isinstance(exc.value.detail["error"], str) and exc.value.detail["error"].strip()


async def test_require_role_accepte_le_meme_role_actif() -> None:
    compte = _utilisateur(202, "admin", ["ADMIN_SCR"])
    assert await require_role("ADMIN_SCR", "ADMIN_DISPATCHING")(current_user=compte) is compte


# ===========================================================================
# D. Compte désactivé (garde)
# ===========================================================================


async def test_compte_desactive_refuse_malgre_un_jeton_valide(client: AsyncClient) -> None:
    compte = _utilisateur(300, "parti", ["CREE_INDICATEURS"], compte_actif=False)
    with _route_droits_atelier(compte) as service:
        response = await client.get(URL_DROITS_ATELIER, headers=_token(compte))
    _verifier_refus(response)
    assert response.json()["detail"]["error"] == "Compte désactivé"
    service.assert_not_awaited()
