"""GET /api/v1/suivi-incidents/filtres — filtres résolus du menu « Suivi incidents ».

Permission ``indicateurs:read`` ; périmètre selon la règle de ``indicateurs_service._resolve_scope`` :
rôles nationaux libres, BCC / BRC limités à leur région (``scope_service_id`` = région),
SUPERVISEUR limité à son service. Période absente → semaine Senelec passée.

Écrits avant le code (circuit « tests avant le code »).
"""

import uuid
from datetime import date
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur

pytestmark = pytest.mark.asyncio

URL = "/api/v1/suivi-incidents/filtres"
LECTURE = [("indicateurs", "read")]


def _make_role(role_name: str, perms: list[tuple[str, str]]) -> Role:
    role = Role()
    role.id = 1
    role.nom = role_name
    role.description = role_name
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(perms, start=1):
        perm = Permission()
        perm.id = i
        perm.ressource = ressource
        perm.action = action
        rp = RolePermission()
        rp.id = i
        rp.role_id = 1
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps
    return role


def _make_user(
    role_name: str,
    perms: list[tuple[str, str]] | None = None,
    scope_service_id: int | None = None,
    user_id: int = 1,
) -> Utilisateur:
    role = _make_role(role_name, LECTURE if perms is None else perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = f"{role_name.lower()}_{user_id}"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = f"{role_name.lower()}_{user_id}@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _headers(user: Utilisateur) -> dict[str, str]:
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom, "service_id": user.user_roles[0].scope_service_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def _get(client: AsyncClient, user: Utilisateur, params: dict[str, object] | None = None):
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user):
        return await client.get(URL, params=params or {}, headers=_headers(user))


# --------------------------------------------------------------------------------------------
# Authentification et validation
# --------------------------------------------------------------------------------------------


async def test_sans_jeton_refuse(client: AsyncClient) -> None:
    """Sans en-tête Authorization : refusé (HTTPBearer de l'application : 403 ; 401 accepté)."""
    response = await client.get(URL)
    assert response.status_code in (401, 403)
    assert response.status_code != 404


async def test_jeton_invalide_401(client: AsyncClient) -> None:
    """Jeton illisible → 401."""
    response = await client.get(URL, headers={"Authorization": "Bearer pas-un-jwt"})
    assert response.status_code == 401


async def test_sans_permission_indicateurs_read_403(client: AsyncClient) -> None:
    """Rôle sans indicateurs:read → 403."""
    user = _make_user("ADMIN_SAQS", perms=[("interruptions_distribution", "read")])
    response = await _get(client, user)
    assert response.status_code == 403


async def test_role_sans_perimetre_indicateurs_403(client: AsyncClient) -> None:
    """DISPATCHER avec indicateurs:read : rôle transport, hors règle des indicateurs distribution → 403."""
    response = await _get(client, _make_user("DISPATCHER"))
    assert response.status_code == 403


async def test_fin_avant_debut_422(client: AsyncClient) -> None:
    """fin < debut → 422."""
    response = await _get(
        client, _make_user("ADMIN_SAQS"), {"debut": "2026-11-20", "fin": "2026-11-14"}
    )
    assert response.status_code == 422


async def test_plage_trop_longue_422(client: AsyncClient) -> None:
    """Plus de trois ans → 422."""
    response = await _get(
        client, _make_user("ADMIN_SAQS"), {"debut": "2020-01-01", "fin": "2026-11-20"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "params",
    [{"service_id": 0}, {"region_id": -1}, {"reseau": "bt"}, {"debut": "pas-une-date"}],
)
async def test_parametres_invalides_422(client: AsyncClient, params: dict[str, object]) -> None:
    """Identifiant ≤ 0, réseau inconnu, date illisible → 422."""
    response = await _get(client, _make_user("ADMIN_SAQS"), params)
    assert response.status_code == 422


# --------------------------------------------------------------------------------------------
# Période et libellé
# --------------------------------------------------------------------------------------------


async def test_sans_dates_semaine_senelec_passee(client: AsyncClient) -> None:
    """debut / fin absents → semaine Senelec passée par rapport à aujourd'hui ; enveloppe standard."""
    from app.services.periodes import semaine_senelec_passee

    attendu = semaine_senelec_passee(date.today())
    response = await _get(client, _make_user("ADMIN_SAQS"))

    assert response.status_code == 200
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["error"] is None
    data = corps["data"]
    assert data["filtres"]["debut"] == attendu.debut.isoformat()
    assert data["filtres"]["fin"] == attendu.fin.isoformat()
    assert data["semaine"] == {
        "numero": attendu.numero,
        "annee": attendu.annee,
        "debut": attendu.debut.isoformat(),
        "fin": attendu.fin.isoformat(),
    }
    assert data["libelle_periode"].startswith(f"S{attendu.numero} · ")


async def test_semaine_senelec_explicite(client: AsyncClient) -> None:
    """Période = exactement une semaine Senelec → semaine renseignée, libellé « S47 · 14/11 → 20/11/2026 »."""
    response = await _get(
        client, _make_user("ADMIN_SAQS"), {"debut": "2026-11-14", "fin": "2026-11-20"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["semaine"] == {"numero": 47, "annee": 2026, "debut": "2026-11-14", "fin": "2026-11-20"}
    assert data["libelle_periode"] == "S47 · 14/11 → 20/11/2026"


async def test_semaine_qui_n_est_pas_la_semaine_passee(client: AsyncClient) -> None:
    """Toute semaine Senelec exacte est reconnue, pas seulement la semaine passée (S43 2026)."""
    response = await _get(
        client, _make_user("ADMIN_SAQS"), {"debut": "2026-10-17", "fin": "2026-10-23"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["semaine"] == {"numero": 43, "annee": 2026, "debut": "2026-10-17", "fin": "2026-10-23"}
    assert data["libelle_periode"] == "S43 · 17/10 → 23/10/2026"


@pytest.mark.parametrize(
    ("debut", "fin", "libelle"),
    [
        ("2026-11-01", "2026-11-25", "01/11 → 25/11/2026"),
        # sept jours mais du dimanche au samedi : pas une semaine Senelec
        ("2026-11-15", "2026-11-21", "15/11 → 21/11/2026"),
        # samedi → vendredi de la semaine suivante (14 jours) : pas une semaine
        ("2026-11-07", "2026-11-20", "07/11 → 20/11/2026"),
    ],
)
async def test_periode_libre(client: AsyncClient, debut: str, fin: str, libelle: str) -> None:
    """Période qui n'est pas une semaine Senelec → semaine null, libellé « jj/mm → jj/mm/aaaa »."""
    response = await _get(client, _make_user("ADMIN_SAQS"), {"debut": debut, "fin": fin})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["semaine"] is None
    assert data["libelle_periode"] == libelle
    assert (data["filtres"]["debut"], data["filtres"]["fin"]) == (debut, fin)


async def test_filtres_renvoyes_complets(client: AsyncClient) -> None:
    """Les filtres reçus sont renvoyés tels quels (types convertis)."""
    params = {
        "debut": "2026-11-01", "fin": "2026-11-25", "poste_source_id": 3, "feeder_id": 4,
        "nature_id": 5, "cause_id": 6, "reseau": "htb", "exogene": "false",
    }
    response = await _get(client, _make_user("ADMIN_SCR"), params)
    assert response.status_code == 200
    filtres = response.json()["data"]["filtres"]
    assert filtres == {
        "debut": "2026-11-01", "fin": "2026-11-25", "region_id": None, "service_id": None,
        "poste_source_id": 3, "feeder_id": 4, "nature_id": 5, "cause_id": 6,
        "reseau": "htb", "exogene": False,
    }


# --------------------------------------------------------------------------------------------
# Périmètre (RBAC)
# --------------------------------------------------------------------------------------------

SEMAINE = {"debut": "2026-11-14", "fin": "2026-11-20"}


@pytest.mark.parametrize("role", ["ADMIN_SAQS", "ADMIN_SCR", "SUPERADMIN"])
async def test_role_national_libre(client: AsyncClient, role: str) -> None:
    """Rôle national sans filtre : niveau national, rien de verrouillé."""
    response = await _get(client, _make_user(role), SEMAINE)
    assert response.status_code == 200
    perimetre = response.json()["data"]["perimetre"]
    assert perimetre == {
        "niveau": "national", "scope_id": None, "region_verrouillee": False, "service_verrouille": False,
    }


async def test_role_national_choisit_une_region(client: AsyncClient) -> None:
    """Rôle national avec region_id : niveau région, non verrouillé."""
    response = await _get(client, _make_user("ADMIN_SAQS"), {**SEMAINE, "region_id": 2})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["perimetre"] == {
        "niveau": "region", "scope_id": 2, "region_verrouillee": False, "service_verrouille": False,
    }
    assert data["filtres"]["region_id"] == 2


@pytest.mark.parametrize("role", ["BRC", "BCC"])
async def test_role_regional_region_imposee(client: AsyncClient, role: str) -> None:
    """BRC / BCC sans region_id : sa région est imposée et verrouillée."""
    response = await _get(client, _make_user(role, scope_service_id=2), SEMAINE)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["perimetre"] == {
        "niveau": "region", "scope_id": 2, "region_verrouillee": True, "service_verrouille": False,
    }
    assert data["filtres"]["region_id"] == 2


@pytest.mark.parametrize("role", ["BRC", "BCC"])
async def test_role_regional_sa_propre_region(client: AsyncClient, role: str) -> None:
    """BRC / BCC qui demande sa propre région : autorisé."""
    response = await _get(client, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 2})
    assert response.status_code == 200
    assert response.json()["data"]["filtres"]["region_id"] == 2


@pytest.mark.parametrize("role", ["BRC", "BCC"])
async def test_role_regional_autre_region_403(client: AsyncClient, role: str) -> None:
    """BRC / BCC qui demande une autre région → 403."""
    response = await _get(client, _make_user(role, scope_service_id=2), {**SEMAINE, "region_id": 1})
    assert response.status_code == 403


async def test_brc_sans_region_configuree_403(client: AsyncClient) -> None:
    """BRC sans scope_service_id → 403 (périmètre non configuré)."""
    response = await _get(client, _make_user("BRC", scope_service_id=None), SEMAINE)
    assert response.status_code == 403


async def test_superviseur_service_impose(client: AsyncClient) -> None:
    """SUPERVISEUR : son service imposé et verrouillé."""
    response = await _get(client, _make_user("SUPERVISEUR", scope_service_id=5), SEMAINE)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["perimetre"] == {
        "niveau": "service", "scope_id": 5, "region_verrouillee": False, "service_verrouille": True,
    }
    assert data["filtres"]["service_id"] == 5


async def test_superviseur_son_propre_service(client: AsyncClient) -> None:
    """SUPERVISEUR qui demande son propre service : autorisé."""
    response = await _get(
        client, _make_user("SUPERVISEUR", scope_service_id=5), {**SEMAINE, "service_id": 5}
    )
    assert response.status_code == 200
    assert response.json()["data"]["filtres"]["service_id"] == 5


async def test_superviseur_autre_service_403(client: AsyncClient) -> None:
    """SUPERVISEUR qui demande un autre service → 403."""
    response = await _get(
        client, _make_user("SUPERVISEUR", scope_service_id=5), {**SEMAINE, "service_id": 6}
    )
    assert response.status_code == 403


async def test_superviseur_filtre_region_403(client: AsyncClient) -> None:
    """SUPERVISEUR avec region_id → 403 (même règle que les indicateurs)."""
    response = await _get(
        client, _make_user("SUPERVISEUR", scope_service_id=5), {**SEMAINE, "region_id": 1}
    )
    assert response.status_code == 403
