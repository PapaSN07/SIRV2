"""Tests d'intégration — rapport mensuel transport (phase 6.3)."""

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
    role = _make_role(user_id, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = user_id
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
def admin_dispatching() -> Utilisateur:
    return _make_user(
        1,
        "ADMIN_DISPATCHING",
        [("rapports", "read"), ("interruptions_transport", "read")],
        scope=None,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(
        2,
        "BCC",
        [("rapports", "read"), ("interruptions_distribution", "read")],
        scope=1,
    )


async def test_admin_dispatching_post_mensuel_transport_returns_202(
    client: AsyncClient,
    admin_dispatching: Utilisateur,
) -> None:
    payload = RapportEnqueueResponse(
        task_id="task-transport-1",
        type_rapport="mensuel_transport",
        statut="pending",
        format="pdf",
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=admin_dispatching,
    ), patch(
        "app.services.rapport_generation_service.enqueue_mensuel_transport",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.post(
            "/api/v1/rapports/mensuel/transport?annee=2026&mois=6&format=pdf",
            headers=_auth_headers(_token(admin_dispatching, "ADMIN_DISPATCHING")),
        )

    assert response.status_code == 202
    body = response.json()
    assert body["data"]["task_id"] == "task-transport-1"
    assert body["data"]["type_rapport"] == "mensuel_transport"


async def test_bcc_post_mensuel_transport_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.post(
            "/api/v1/rapports/mensuel/transport?annee=2026&mois=6&format=pdf",
            headers=_auth_headers(_token(bcc_user, "BCC")),
        )

    assert response.status_code == 403
