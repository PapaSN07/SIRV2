"""Tests d'intégration — endpoints admin utilisateurs (phase 1.5).

Couverture TODO §1.5 :
  - Admin SCR liste utilisateurs distribution → 200
  - Admin Dispatching accès utilisateur distribution → 403
  - BCC accès endpoint admin → 403
  - Création utilisateur → 201 + premiere_connexion=True
  - Reset password → login avec nouveau mot de passe OK
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.admin import UtilisateurResponse
from app.schemas.common import PaginatedResponse

pytestmark = pytest.mark.asyncio

_ADMIN_PERMISSIONS = [
    ("admin_utilisateurs", "read"),
    ("admin_utilisateurs", "create"),
    ("admin_utilisateurs", "update"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_permission(ressource: str, action: str, perm_id: int) -> Permission:
    perm = Permission()
    perm.id = perm_id
    perm.ressource = ressource
    perm.action = action
    perm.description = f"{ressource}:{action}"
    return perm


def _make_role_with_admin_perms(nom: str, role_id: int) -> Role:
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = f"Rôle {nom}"
    role.is_active = True

    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(_ADMIN_PERMISSIONS, start=1):
        perm = _make_permission(ressource, action, i)
        rp = RolePermission()
        rp.id = i
        rp.role_id = role_id
        rp.permission_id = perm.id
        rp.role = role
        rp.permission = perm
        rps.append(rp)

    role.role_permissions = rps
    return role


def _make_user(
    user_id: int,
    login: str,
    role_nom: str,
    role_id: int,
    scope_service_id: int | None = None,
    password: str = "MotDePasse123!",
    premiere_connexion: bool = False,
) -> Utilisateur:
    role = _make_role_with_admin_perms(role_nom, role_id)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role_id
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = hash_password(password)
    user.nom = "Admin"
    user.prenom = "Test"
    user.email = f"{login}@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = premiere_connexion
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _make_bcc_user(user_id: int = 10) -> Utilisateur:
    role = Role()
    role.id = 10
    role.nom = "BCC"
    role.description = "BCC"
    role.is_active = True
    role.role_permissions = []

    perm = _make_permission("interruptions_distribution", "create", 99)
    rp = RolePermission()
    rp.id = 99
    rp.role_id = role.id
    rp.permission_id = perm.id
    rp.role = role
    rp.permission = perm
    role.role_permissions = [rp]

    ur = UserRole()
    ur.id = 10
    ur.utilisateur_id = user_id
    ur.role_id = role.id
    ur.scope_service_id = 1
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = "bcc_user"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "BCC"
    user.prenom = "User"
    user.email = "bcc@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _token_for(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom},
    )


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(1, "admin_scr", "ADMIN_SCR", role_id=1)


@pytest.fixture
def admin_dispatching() -> Utilisateur:
    return _make_user(2, "admin_dispatch", "ADMIN_DISPATCHING", role_id=2)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_bcc_user()


# ---------------------------------------------------------------------------
# Admin SCR liste → 200
# ---------------------------------------------------------------------------


async def test_admin_scr_list_utilisateurs_returns_200(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[
            UtilisateurResponse(
                id=10,
                login="bcc_new",
                nom="Ndiaye",
                prenom="Fatou",
                email=None,
                telephone=None,
                is_active=True,
                premiere_connexion=True,
                roles=[],
            )
        ],
        total=1,
        page=1,
        page_size=20,
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=admin_scr,
    ), patch(
        "app.services.admin_utilisateur_service.list_utilisateurs",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/admin/utilisateurs",
            headers=_auth_headers(_token_for(admin_scr)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["login"] == "bcc_new"


# ---------------------------------------------------------------------------
# BCC accès admin → 403
# ---------------------------------------------------------------------------


async def test_bcc_access_admin_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ):
        response = await client.get(
            "/api/v1/admin/utilisateurs",
            headers=_auth_headers(_token_for(bcc_user)),
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert "admin_utilisateurs" in detail["error"]


# ---------------------------------------------------------------------------
# Admin Dispatching accès utilisateur distribution → 403
# ---------------------------------------------------------------------------


async def test_admin_dispatching_update_distribution_user_returns_403(
    client: AsyncClient,
    admin_dispatching: Utilisateur,
    bcc_user: Utilisateur,
) -> None:
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        side_effect=lambda db, uid: admin_dispatching if uid == admin_dispatching.id else bcc_user,
    ), patch(
        "app.repositories.admin_utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ):
        response = await client.put(
            f"/api/v1/admin/utilisateurs/{bcc_user.id}",
            headers=_auth_headers(_token_for(admin_dispatching)),
            json={"nom": "Tentative"},
        )

    assert response.status_code == 403
    assert "périmètre" in response.json()["detail"]["error"].lower()


# ---------------------------------------------------------------------------
# Création utilisateur → 201 + premiere_connexion=True
# ---------------------------------------------------------------------------


async def test_admin_scr_create_utilisateur_returns_201(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    created = UtilisateurResponse(
        id=20,
        login="nouveau_bcc",
        nom="Sarr",
        prenom="Ibrahima",
        email="ibrahima@senelec.sn",
        telephone=None,
        is_active=True,
        premiere_connexion=True,
        roles=[{"role_id": 10, "role_nom": "BCC", "scope_service_id": 1}],
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=admin_scr,
    ), patch(
        "app.services.admin_utilisateur_service.create_utilisateur",
        new_callable=AsyncMock,
        return_value=created,
    ):
        response = await client.post(
            "/api/v1/admin/utilisateurs",
            headers=_auth_headers(_token_for(admin_scr)),
            json={
                "login": "nouveau_bcc",
                "password": "MotDePasse123!",
                "nom": "Sarr",
                "prenom": "Ibrahima",
                "email": "ibrahima@senelec.sn",
                "roles": [{"role_id": 10, "scope_service_id": 1}],
            },
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["login"] == "nouveau_bcc"
    assert data["premiere_connexion"] is True


# ---------------------------------------------------------------------------
# Reset password → login avec nouveau mot de passe OK
# ---------------------------------------------------------------------------


async def test_reset_password_then_login_ok(
    client: AsyncClient,
    admin_scr: Utilisateur,
    bcc_user: Utilisateur,
    fake_redis: Any,
) -> None:
    new_password = "NouveauMotDePasse1!"

    async def _get_by_id_side_effect(db, uid):
        if uid == admin_scr.id:
            return admin_scr
        if uid == bcc_user.id:
            return bcc_user
        return None

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        side_effect=_get_by_id_side_effect,
    ), patch(
        "app.repositories.admin_utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.repositories.admin_utilisateur_repository.reset_password",
        new_callable=AsyncMock,
    ) as mock_reset, patch(
        "app.services.admin_utilisateur_service.log_audit",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            f"/api/v1/admin/utilisateurs/{bcc_user.id}/reset-password",
            headers=_auth_headers(_token_for(admin_scr)),
            json={"new_password": new_password},
        )

    assert response.status_code == 204
    mock_reset.assert_awaited_once()

    # Simuler l'utilisateur après reset (nouveau hash, premiere_connexion=False)
    bcc_user.password_hash = hash_password(new_password)
    bcc_user.premiere_connexion = False

    with patch(
        "app.repositories.utilisateur_repository.get_by_login",
        return_value=bcc_user,
    ):
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"login": bcc_user.login, "password": new_password},
        )

    assert login_response.status_code == 200
    assert login_response.json()["data"]["access_token"]
