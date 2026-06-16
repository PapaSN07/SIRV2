"""Tests d'intégration — rapport journalier (phase 6.1)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.rapports import RapportEnqueueResponse

pytestmark = pytest.mark.asyncio


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_role(role_id: int, role_name: str, perms: list[tuple[str, str]]) -> Role:
    role = Role()
    role.id = role_id
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
        rp.role_id = role_id
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps
    return role


def _make_user(
    user_id: int,
    role_name: str,
    perms: list[tuple[str, str]],
    scope: int | None = None,
) -> Utilisateur:
    role = _make_role(1, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope
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


def _token(user: Utilisateur, role_name: str) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": role_name, "service_id": user.user_roles[0].scope_service_id},
    )


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(1, "ADMIN_SAQS", [("rapports", "read")], scope=None)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(2, "BCC", [("rapports", "read")], scope=1)


async def test_post_journalier_valid_date_returns_202(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = RapportEnqueueResponse(
        task_id="task-journalier-1",
        type_rapport="journalier",
        statut="pending",
        format="pdf",
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.rapport_generation_service.enqueue_journalier",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.post(
            "/api/v1/rapports/journalier",
            json={"date": "2026-06-12", "format": "pdf"},
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 202
    body = response.json()
    assert body["data"]["task_id"] == "task-journalier-1"
    assert body["data"]["type_rapport"] == "journalier"


async def test_post_journalier_invalid_date_returns_422(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs):
        response = await client.post(
            "/api/v1/rapports/journalier",
            json={"date": "not-a-date", "format": "pdf"},
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 422


async def test_bcc_post_journalier_with_region_id_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.post(
            "/api/v1/rapports/journalier",
            json={"date": "2026-06-12", "region_id": 2, "format": "pdf"},
            headers=_auth_headers(_token(bcc_user, "BCC")),
        )

    assert response.status_code == 403
