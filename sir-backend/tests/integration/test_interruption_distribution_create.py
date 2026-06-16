"""Tests d'intégration — création interruption distribution (phase 3.1)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import InterruptionDistributionResponse

pytestmark = pytest.mark.asyncio

_DISTRIB_CREATE_PERMS = [
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "update"),
]

_TRANSPORT_CREATE_PERMS = [
    ("interruptions_transport", "create"),
    ("interruptions_transport", "read"),
    ("interruptions_transport", "update"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_role(nom: str, role_id: int, permissions: list[tuple[str, str]]) -> Role:
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = nom
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(permissions, start=1):
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
    login: str,
    role_nom: str,
    role_id: int,
    permissions: list[tuple[str, str]],
    scope_service_id: int | None = None,
) -> Utilisateur:
    role = _make_role(role_nom, role_id, permissions)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role_id
    ur.scope_service_id = scope_service_id
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = login
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = f"{login}@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _token(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom, "service_id": user.user_roles[0].scope_service_id},
    )


def _valid_payload() -> dict[str, object]:
    return {
        "date_apparition": "2026-06-12T10:30:00",
        "feeder_id": 1,
        "cause_id": 1,
        "nature_id": 1,
        "siege_id": 1,
        "signalisation_id": 1,
    }


def _sample_response() -> InterruptionDistributionResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionDistributionResponse(
        id=1,
        numero_interruption=42,
        type_direction="distribution",
        statut="en_cours",
        service_id=1,
        feeder_id=1,
        poste_source_id=1,
        date_apparition=now,
        date_remise=None,
        duree_minutes=None,
        cause_id=1,
        nature_id=1,
        siege_id=1,
        signalisation_id=1,
        puissance_coupee_mw=None,
        localisation=None,
        observations=None,
        is_force_majeure=False,
        is_fugitive=False,
        created_by_id=1,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, _DISTRIB_CREATE_PERMS, scope_service_id=1)


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(2, "dispatcher", "DISPATCHER", 2, _TRANSPORT_CREATE_PERMS, scope_service_id=None)


async def test_bcc_create_interruption_own_service_returns_201(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.create",
        new_callable=AsyncMock,
        return_value=_sample_response(),
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json=_valid_payload(),
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["statut"] == "en_cours"
    assert body["data"]["numero_interruption"] == 42


async def test_bcc_create_feeder_other_service_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _raise_scope(*_args, **_kwargs):
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "data": None, "error": "Hors périmètre : service_id non autorisé"},
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.create",
        side_effect=_raise_scope,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json={**_valid_payload(), "feeder_id": 99},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403


async def test_create_missing_required_fields_returns_422(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json={"date_apparition": "2026-06-12T10:30:00"},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 422


async def test_dispatcher_post_distribution_returns_403(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json=_valid_payload(),
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 403
