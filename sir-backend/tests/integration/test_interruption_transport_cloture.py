"""Tests d'intégration — clôture interruption transport (phase 4.3)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_transport import InterruptionTransportResponse

pytestmark = pytest.mark.asyncio

_UPDATE_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "update"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(user_id: int = 2) -> Utilisateur:
    role = Role()
    role.id = 2
    role.nom = "DISPATCHER"
    role.description = "DISPATCHER"
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(_UPDATE_PERMS, start=1):
        perm = Permission()
        perm.id = i
        perm.ressource = ressource
        perm.action = action
        rp = RolePermission()
        rp.id = i
        rp.role_id = 2
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 2
    ur.scope_service_id = None
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = "dispatcher"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = "dispatcher@senelec.sn"
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
        extra={"role": "DISPATCHER", "service_id": None},
    )


def _cloture_response() -> InterruptionTransportResponse:
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 30, 0)
    return InterruptionTransportResponse(
        id=1,
        numero_interruption=7,
        type_direction="transport",
        statut="cloture",
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
        energie_non_fournie_mwh=None,
        created_by_id=2,
        created_at=apparition,
        updated_at=remise,
    )


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user()


async def test_cloture_invalid_date_remise_returns_422(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "date_remise doit être postérieure à date_apparition",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.cloturer",
        side_effect=_reject,
    ):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/cloturer",
            json={"date_remise": "2026-06-12T09:00:00"},
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 422


async def test_cloture_ok_returns_200(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.cloturer",
        new_callable=AsyncMock,
        return_value=_cloture_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/transport/1/cloturer",
            json={"date_remise": "2026-06-12T12:30:00"},
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["statut"] == "cloture"
    assert data["duree_minutes"] == 150


async def test_cloture_enqueues_calcul_end_task(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.cloturer",
        new_callable=AsyncMock,
        return_value=_cloture_response(),
    ) as mock_cloturer:
        await client.patch(
            "/api/v1/interruptions/transport/1/cloturer",
            json={"date_remise": "2026-06-12T12:30:00"},
            headers=_auth_headers(_token(dispatcher)),
        )

    mock_cloturer.assert_awaited_once()
