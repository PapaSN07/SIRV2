"""Tests d'intégration — destinataires notifications (phase 8.3)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.notifications import DestinataireResponse

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
def admin_scr() -> Utilisateur:
    return _make_user(
        1,
        "ADMIN_SCR",
        [("notifications", "read"), ("notifications", "admin")],
        scope=None,
    )


async def test_post_destinataire_returns_201(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    payload = DestinataireResponse(
        id=1,
        nom="Alertes Test",
        telephone="+221770000099",
        email="alertes.test@senelec.sn",
        utilisateur_id=None,
        service_id=1,
        is_active=True,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_scr), patch(
        "app.services.destinataire_service.create_destinataire",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.post(
            "/api/v1/notifications/destinataires",
            json={
                "nom": "Alertes Test",
                "telephone": "+221770000099",
                "email": "alertes.test@senelec.sn",
                "service_id": 1,
            },
            headers=_auth_headers(_token(admin_scr, "ADMIN_SCR")),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["nom"] == "Alertes Test"


async def test_post_destinataire_without_admin_permission_returns_403(
    client: AsyncClient,
) -> None:
    reader = _make_user(2, "ADMIN_SAQS", [("notifications", "read")], scope=None)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=reader):
        response = await client.post(
            "/api/v1/notifications/destinataires",
            json={
                "nom": "Alertes Test",
                "email": "test@senelec.sn",
            },
            headers=_auth_headers(_token(reader, "ADMIN_SAQS")),
        )

    assert response.status_code == 403
