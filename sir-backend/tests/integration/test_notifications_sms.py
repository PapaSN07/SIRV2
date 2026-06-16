"""Tests d'intégration — SMS notifications (Phase 7)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.notifications import Destinataire, SmsEnvoye
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse

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
    role = _make_role(1, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = None
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = f"{role_name.lower()}_{user_id}"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = f"{role_name.lower()}_{user_id}@senelec.sn"
    user.telephone = "+221771234567"
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


async def test_send_manual_sms_to_destinataire(client: AsyncClient) -> None:
    admin = _make_user(
        1,
        "ADMIN_SCR",
        [("notifications", "read"), ("notifications", "admin")],
    )
    dest = Destinataire()
    dest.id = 10
    dest.nom = "Agent Test"
    dest.telephone = "+221771111111"
    dest.email = None
    dest.utilisateur_id = None
    dest.service_id = 1
    dest.is_active = True

    sms_record = SmsEnvoye()
    sms_record.id = 99
    sms_record.destinataire_id = 10
    sms_record.entity_type = "manual"
    sms_record.entity_id = None
    sms_record.contenu = "Test SMS manuel"
    sms_record.statut = "en_attente"

    with (
        patch(
            "app.repositories.utilisateur_repository.get_by_id",
            new=AsyncMock(return_value=admin),
        ),
        patch(
            "app.repositories.destinataire_repository.get_by_id",
            new=AsyncMock(return_value=dest),
        ),
        patch(
            "app.services.destinataire_service.assert_destinataire_in_scope",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.repositories.sms_repository.create_pending",
            new=AsyncMock(return_value=sms_record),
        ),
        patch(
            "app.workers.celery_app.celery_app.send_task",
            MagicMock(),
        ) as mock_send,
    ):
        response = await client.post(
            "/api/v1/notifications/sms/send",
            headers=_auth_headers(_token(admin, "ADMIN_SCR")),
            json={"message": "Test SMS manuel", "destinataire_ids": [10]},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["sent_count"] == 1
    assert data["sms_ids"] == [99]
    mock_send.assert_called_once_with("envoi_sms", args=[99])


async def test_list_sms_returns_200(client: AsyncClient) -> None:
    reader = _make_user(2, "ADMIN_SAQS", [("notifications", "read")])
    empty = PaginatedResponse(items=[], total=0, page=1, page_size=20)
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        new=AsyncMock(return_value=reader),
    ), patch(
        "app.services.notification_trace_service.list_sms",
        new=AsyncMock(return_value=empty),
    ):
        response = await client.get(
            "/api/v1/notifications/sms",
            headers=_auth_headers(_token(reader, "ADMIN_SAQS")),
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "items" in body["data"]
