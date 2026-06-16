"""Tests d'intégration — rapport annuel (phase 6.4)."""

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


def _make_user(user_id: int, role_name: str, perms: list[tuple[str, str]]) -> Utilisateur:
    role = _make_role(user_id, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = user_id
    ur.scope_service_id = None
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
        extra={"role": role_name, "service_id": None},
    )


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(1, "ADMIN_SAQS", [("rapports", "read")])


async def test_post_annuel_valid_year_returns_202(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = RapportEnqueueResponse(
        task_id="task-annuel-1",
        type_rapport="annuel",
        statut="pending",
        format="pdf",
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.rapport_generation_service.enqueue_annuel",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.post(
            "/api/v1/rapports/annuel?annee=2026&direction=distribution&format=pdf",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 202
    body = response.json()
    assert body["data"]["task_id"] == "task-annuel-1"
    assert body["data"]["type_rapport"] == "annuel"


async def test_post_annuel_invalid_direction_returns_422(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs):
        response = await client.post(
            "/api/v1/rapports/annuel?annee=2026&direction=invalid&format=pdf",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 422
