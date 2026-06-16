"""Tests d'intégration — validation interruption transport (phase 4.4)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_transport import InterruptionTransportResponse

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
) -> Utilisateur:
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


def _valide_response() -> InterruptionTransportResponse:
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 30, 0)
    return InterruptionTransportResponse(
        id=1,
        numero_interruption=7,
        type_direction="transport",
        statut="valide",
        service_id=None,
        date_apparition=apparition,
        date_remise=remise,
        duree_minutes=150,
        cause_id=1,
        nature_id=1,
        siege_id=1,
        signalisation_id=1,
        puissance_coupee_mw=50.0,
        localisation=None,
        observations=None,
        is_force_majeure=False,
        is_fugitive=False,
        tension_kv=225.0,
        equipement_transport_id=1,
        source_transport_id=1,
        puissance_transit_mw=150.0,
        energie_non_fournie_mwh=12.5,
        created_by_id=2,
        created_at=apparition,
        updated_at=remise,
    )


_ADMIN_DISPATCHING_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "create"),
    ("interruptions_transport", "update"),
    ("interruptions_transport", "validate"),
]

_ADMIN_SAQS_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "validate"),
]

_DISPATCHER_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "create"),
    ("interruptions_transport", "update"),
]


async def test_admin_dispatching_valide_cloturee_returns_200(client: AsyncClient) -> None:
    user = _make_user(4, "ADMIN_DISPATCHING", _ADMIN_DISPATCHING_PERMS)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_transport_service.valider",
        new_callable=AsyncMock,
        return_value=_valide_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/valider",
            headers=_auth_headers(_token(user, "ADMIN_DISPATCHING")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["statut"] == "valide"


async def test_admin_saqs_valide_returns_200(client: AsyncClient) -> None:
    user = _make_user(5, "ADMIN_SAQS", _ADMIN_SAQS_PERMS)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_transport_service.valider",
        new_callable=AsyncMock,
        return_value=_valide_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/valider",
            headers=_auth_headers(_token(user, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["statut"] == "valide"


async def test_dispatcher_valider_returns_403(client: AsyncClient) -> None:
    user = _make_user(2, "DISPATCHER", _DISPATCHER_PERMS)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/valider",
            headers=_auth_headers(_token(user, "DISPATCHER")),
        )

    assert response.status_code == 403


async def test_valider_en_cours_returns_422(client: AsyncClient) -> None:
    user = _make_user(4, "ADMIN_DISPATCHING", _ADMIN_DISPATCHING_PERMS)

    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "Validation autorisée uniquement pour une interruption cloture",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_transport_service.valider",
        side_effect=_reject,
    ):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/valider",
            headers=_auth_headers(_token(user, "ADMIN_DISPATCHING")),
        )

    assert response.status_code == 422
