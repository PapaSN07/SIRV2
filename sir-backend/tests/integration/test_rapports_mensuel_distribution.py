"""Tests d'intégration — rapport mensuel distribution (phase 6.2)."""

import uuid
from pathlib import Path
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


async def test_post_mensuel_distribution_valid_period_returns_202(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = RapportEnqueueResponse(
        task_id="task-mensuel-1",
        type_rapport="mensuel_distribution",
        statut="pending",
        format="pdf",
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.rapport_generation_service.enqueue_mensuel_distribution",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.post(
            "/api/v1/rapports/mensuel/distribution?annee=2026&mois=6&format=pdf",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 202
    body = response.json()
    assert body["data"]["task_id"] == "task-mensuel-1"
    assert body["data"]["type_rapport"] == "mensuel_distribution"


async def test_download_mensuel_distribution_pdf_content_type(
    client: AsyncClient,
    admin_saqs: Utilisateur,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "mensuel_task-mensuel-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 test")

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.rapport_generation_service.resolve_download",
        new_callable=AsyncMock,
        return_value=(pdf_path, "mensuel_task-mensuel-1.pdf", "application/pdf"),
    ):
        response = await client.get(
            "/api/v1/rapports/task-mensuel-1/download",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
