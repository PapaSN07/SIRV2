"""Tests d'intégration — périmètre des admins sur les comptes à plusieurs rôles.

Faille visée : `user_has_direction_role` accepte une cible dès qu'UN de ses rôles
appartient à la direction de l'admin (ou est un rôle créé dans la matrice). Un
Admin Dispatching peut ainsi réinitialiser le mot de passe d'un compte
DISPATCHER + ADMIN_SCR, ou d'un SUPERADMIN qui porte aussi un rôle créé.

Règle attendue : un admin non superadmin n'agit sur un compte (profil,
activation / désactivation, mot de passe, rôles) que si la cible a au moins un
rôle et que TOUS ses rôles système (ROLES_SYSTEME) sont dans sa direction ; les
rôles créés de la matrice ne gênent pas ; jamais si la cible détient SUPERADMIN
ou ADMIN_SAQS. Refus = 403 enveloppé, sans écriture ni audit. SUPERADMIN garde
tous les droits.
"""

import uuid
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, Response

from app.core.security import create_access_token
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.repositories import admin_utilisateur_repository as admin_repo

pytestmark = pytest.mark.asyncio

# Identifiants des rôles (fixes pour tout le module)
ROLE_IDS: dict[str, int] = {
    "ADMIN_SCR": 1,
    "ADMIN_DISPATCHING": 2,
    "SUPERADMIN": 3,
    "BCC": 10,
    "BRC": 11,
    "SUPERVISEUR": 12,
    "DISPATCHER": 13,
    "ADMIN_SAQS": 14,
    "LECTEUR_RAPPORTS": 50,  # rôle créé dans la matrice, hors ROLES_SYSTEME
}

_ROLES_AVEC_SCOPE = {"BCC", "BRC", "SUPERVISEUR"}

_ADMIN_PERMISSIONS = [
    ("admin_utilisateurs", "read"),
    ("admin_utilisateurs", "create"),
    ("admin_utilisateurs", "update"),
]

URL = "/api/v1/admin/utilisateurs"
NOUVEAU_MDP = {"new_password": "NouveauMotDePasse1!"}


# ---------------------------------------------------------------------------
# Construction des objets en mémoire
# ---------------------------------------------------------------------------


def _role(nom: str, avec_permissions_admin: bool = False) -> Role:
    role = Role()
    role.id = ROLE_IDS[nom]
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = True
    rps: list[RolePermission] = []
    if avec_permissions_admin:
        for i, (ressource, action) in enumerate(_ADMIN_PERMISSIONS, start=1):
            perm = Permission()
            perm.id = i
            perm.ressource = ressource
            perm.action = action
            perm.description = f"{ressource}:{action}"
            rp = RolePermission()
            rp.id = role.id * 100 + i
            rp.role_id = role.id
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
    avec_permissions_admin: bool = False,
) -> Utilisateur:
    """Utilisateur portant PLUSIEURS rôles (scope 1 pour BCC / BRC / SUPERVISEUR)."""
    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = "hash-non-utilise"
    user.nom = "Nom"
    user.prenom = "Prenom"
    user.email = f"{login}@senelec.sn"
    user.telephone = None
    user.matricule = None
    user.is_active = True
    user.premiere_connexion = False
    user.audit_logs = []
    user_roles: list[UserRole] = []
    for i, nom in enumerate(roles, start=1):
        ur = UserRole()
        ur.id = user_id * 10 + i
        ur.utilisateur_id = user_id
        ur.role_id = ROLE_IDS[nom]
        ur.scope_service_id = 1 if nom in _ROLES_AVEC_SCOPE else None
        ur.role = _role(nom, avec_permissions_admin)
        ur.utilisateur = user
        user_roles.append(ur)
    user.user_roles = user_roles
    return user


def _admin_scr() -> Utilisateur:
    return _utilisateur(1, "admin_scr", ["ADMIN_SCR"], avec_permissions_admin=True)


def _admin_dispatching() -> Utilisateur:
    return _utilisateur(2, "admin_dispatch", ["ADMIN_DISPATCHING"], avec_permissions_admin=True)


def _superadmin() -> Utilisateur:
    return _utilisateur(3, "superadmin", ["SUPERADMIN"])


def _cible(roles: list[str], user_id: int = 100) -> Utilisateur:
    return _utilisateur(user_id, f"cible_{user_id}", roles)


def _token(user: Utilisateur) -> dict[str, str]:
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom},
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Mocks des repositories
# ---------------------------------------------------------------------------


@dataclass
class Ecritures:
    reset_password: AsyncMock
    set_active: AsyncMock
    update_profile: AsyncMock
    replace_roles: AsyncMock
    log_audit: AsyncMock

    def verifier_aucune_ecriture(self) -> None:
        self.reset_password.assert_not_awaited()
        self.set_active.assert_not_awaited()
        self.update_profile.assert_not_awaited()
        self.replace_roles.assert_not_awaited()
        self.log_audit.assert_not_awaited()


@contextmanager
def _environnement(acteur: Utilisateur, cible: Utilisateur) -> Iterator[Ecritures]:
    """Utilisateur connecté = acteur ; cible chargée par le repository admin."""

    async def _get_utilisateur(db, uid):  # noqa: ANN001, ANN202
        return acteur if uid == acteur.id else cible

    async def _get_role(db, role_id):  # noqa: ANN001, ANN202
        for nom, rid in ROLE_IDS.items():
            if rid == role_id:
                return _role(nom)
        return None

    async def _update_profile(db, user, **kwargs):  # noqa: ANN001, ANN003, ANN202
        return user

    async def _set_active(db, user_id, is_active):  # noqa: ANN001, ANN202
        cible.is_active = is_active
        return cible

    with ExitStack() as pile:
        pile.enter_context(
            patch("app.repositories.utilisateur_repository.get_by_id", side_effect=_get_utilisateur)
        )
        pile.enter_context(
            patch("app.repositories.admin_utilisateur_repository.get_by_id", new_callable=AsyncMock, return_value=cible)
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
            log_audit=pile.enter_context(
                patch("app.services.admin_utilisateur_service.log_audit", new_callable=AsyncMock)
            ),
        )
        yield ecritures


def _verifier_refus(response: Response, ecritures: Ecritures) -> None:
    assert response.status_code == 403, (
        f"Attendu 403 (hors périmètre), obtenu {response.status_code} : {response.text}"
    )
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["data"] is None
    assert isinstance(detail["error"], str) and detail["error"].strip()
    ecritures.verifier_aucune_ecriture()


async def _reset(client: AsyncClient, acteur: Utilisateur, cible: Utilisateur) -> tuple[Response, Ecritures]:
    with _environnement(acteur, cible) as ecritures:
        response = await client.post(
            f"{URL}/{cible.id}/reset-password", headers=_token(acteur), json=NOUVEAU_MDP
        )
    return response, ecritures


# ---------------------------------------------------------------------------
# Rouges : réinitialisation du mot de passe hors périmètre
# ---------------------------------------------------------------------------


async def test_admin_dispatching_ne_reinitialise_pas_le_mdp_d_un_dispatcher_qui_est_aussi_admin_scr(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _admin_dispatching(), _cible(["DISPATCHER", "ADMIN_SCR"]))
    _verifier_refus(response, ecritures)


async def test_admin_dispatching_ne_reinitialise_pas_le_mdp_d_un_superadmin_portant_un_role_cree(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _admin_dispatching(), _cible(["SUPERADMIN", "LECTEUR_RAPPORTS"]))
    _verifier_refus(response, ecritures)


async def test_admin_scr_ne_reinitialise_pas_le_mdp_d_un_bcc_qui_est_aussi_admin_saqs(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _admin_scr(), _cible(["BCC", "ADMIN_SAQS"]))
    _verifier_refus(response, ecritures)


# ---------------------------------------------------------------------------
# Rouges : activation / désactivation hors périmètre
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["desactiver", "activer"])
async def test_admin_scr_n_active_ni_ne_desactive_un_bcc_qui_est_aussi_dispatcher(
    client: AsyncClient, action: str
) -> None:
    acteur, cible = _admin_scr(), _cible(["BCC", "DISPATCHER"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.patch(f"{URL}/{cible.id}/{action}", headers=_token(acteur))
    _verifier_refus(response, ecritures)


# ---------------------------------------------------------------------------
# Rouges : modification du profil et des rôles hors périmètre
# ---------------------------------------------------------------------------


async def test_admin_dispatching_ne_modifie_pas_le_profil_d_un_dispatcher_qui_est_aussi_admin_scr(
    client: AsyncClient,
) -> None:
    acteur, cible = _admin_dispatching(), _cible(["DISPATCHER", "ADMIN_SCR"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.put(f"{URL}/{cible.id}", headers=_token(acteur), json={"nom": "Tentative"})
    _verifier_refus(response, ecritures)


async def test_admin_dispatching_ne_retire_pas_le_role_admin_scr_d_une_cible_mixte(
    client: AsyncClient,
) -> None:
    acteur, cible = _admin_dispatching(), _cible(["DISPATCHER", "ADMIN_SCR"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.put(
            f"{URL}/{cible.id}",
            headers=_token(acteur),
            json={"roles": [{"role_id": ROLE_IDS["DISPATCHER"], "scope_service_id": None}]},
        )
    _verifier_refus(response, ecritures)


async def test_admin_scr_ne_remplace_pas_les_roles_d_un_superadmin_portant_un_role_cree(
    client: AsyncClient,
) -> None:
    acteur, cible = _admin_scr(), _cible(["LECTEUR_RAPPORTS", "SUPERADMIN"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.put(
            f"{URL}/{cible.id}",
            headers=_token(acteur),
            json={"roles": [{"role_id": ROLE_IDS["LECTEUR_RAPPORTS"], "scope_service_id": None}]},
        )
    _verifier_refus(response, ecritures)


# ---------------------------------------------------------------------------
# Gardes vertes : actions légitimes dans le périmètre
# ---------------------------------------------------------------------------


async def test_admin_scr_reinitialise_le_mdp_d_un_bcc_superviseur(client: AsyncClient) -> None:
    response, ecritures = await _reset(client, _admin_scr(), _cible(["BCC", "SUPERVISEUR"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()
    ecritures.log_audit.assert_awaited_once()


async def test_admin_scr_reinitialise_le_mdp_d_un_bcc_portant_un_role_cree(client: AsyncClient) -> None:
    response, ecritures = await _reset(client, _admin_scr(), _cible(["BCC", "LECTEUR_RAPPORTS"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


async def test_admin_dispatching_reinitialise_le_mdp_d_un_compte_avec_seulement_un_role_cree(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _admin_dispatching(), _cible(["LECTEUR_RAPPORTS"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


async def test_admin_dispatching_desactive_un_dispatcher(client: AsyncClient) -> None:
    acteur, cible = _admin_dispatching(), _cible(["DISPATCHER"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.patch(f"{URL}/{cible.id}/desactiver", headers=_token(acteur))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False
    ecritures.set_active.assert_awaited_once()
    ecritures.log_audit.assert_awaited_once()


async def test_admin_scr_remplace_le_role_brc_par_bcc(client: AsyncClient) -> None:
    acteur, cible = _admin_scr(), _cible(["BRC"])
    with _environnement(acteur, cible) as ecritures:
        response = await client.put(
            f"{URL}/{cible.id}",
            headers=_token(acteur),
            json={"roles": [{"role_id": ROLE_IDS["BCC"], "scope_service_id": 1}]},
        )
    assert response.status_code == 200, response.text
    ecritures.replace_roles.assert_awaited_once()
    assert ecritures.replace_roles.await_args.args[1:] == (cible.id, [(ROLE_IDS["BCC"], 1)])


async def test_superadmin_reinitialise_le_mdp_d_un_dispatcher_qui_est_aussi_admin_scr(
    client: AsyncClient,
) -> None:
    response, ecritures = await _reset(client, _superadmin(), _cible(["DISPATCHER", "ADMIN_SCR"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


async def test_superadmin_reinitialise_le_mdp_d_un_autre_superadmin(client: AsyncClient) -> None:
    response, ecritures = await _reset(client, _superadmin(), _cible(["SUPERADMIN"]))
    assert response.status_code == 204, response.text
    ecritures.reset_password.assert_awaited_once()


async def test_admin_dispatching_ne_reinitialise_pas_le_mdp_d_un_bcc(client: AsyncClient) -> None:
    """Non-régression : cible entièrement distribution → 403 (déjà le cas)."""
    response, ecritures = await _reset(client, _admin_dispatching(), _cible(["BCC"]))
    _verifier_refus(response, ecritures)


# ---------------------------------------------------------------------------
# Unitaires : user_has_direction_role(user, direction) — signature actuelle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roles", "direction", "attendu"),
    [
        pytest.param(["BCC", "SUPERVISEUR"], "distribution", True, id="bcc_superviseur_en_distribution"),
        pytest.param(["BCC", "LECTEUR_RAPPORTS"], "distribution", True, id="bcc_et_role_cree_en_distribution"),
        pytest.param(["DISPATCHER"], "transport", True, id="dispatcher_seul_en_transport"),
        pytest.param(["LECTEUR_RAPPORTS"], "transport", True, id="role_cree_seul_en_transport"),
        pytest.param(["DISPATCHER", "ADMIN_SCR"], "transport", False, id="dispatcher_admin_scr_en_transport"),
        pytest.param(["BCC", "DISPATCHER"], "distribution", False, id="bcc_dispatcher_en_distribution"),
        pytest.param(["BCC", "ADMIN_SAQS"], "distribution", False, id="bcc_admin_saqs_en_distribution"),
        pytest.param(["SUPERADMIN", "LECTEUR_RAPPORTS"], "transport", False, id="superadmin_role_cree_en_transport"),
        pytest.param(["SUPERADMIN", "LECTEUR_RAPPORTS"], "distribution", False, id="superadmin_role_cree_en_distribution"),
        pytest.param([], "distribution", False, id="aucun_role_en_distribution"),
        pytest.param([], "transport", False, id="aucun_role_en_transport"),
    ],
)
async def test_user_has_direction_role_exige_tous_les_roles_systeme_dans_la_direction(
    roles: list[str], direction: str, attendu: bool
) -> None:
    assert admin_repo.user_has_direction_role(_cible(roles), direction) is attendu
