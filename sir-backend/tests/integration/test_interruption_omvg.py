"""Tests d'intégration — interruptions OMVG (phase 4.5)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.repositories.interruption_transport_repository import next_numero_interruption
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_transport import InterruptionTransportResponse

pytestmark = pytest.mark.asyncio

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


def _make_dispatcher(user_id: int = 2) -> Utilisateur:
    role = _make_role("DISPATCHER", 2, _TRANSPORT_CREATE_PERMS)
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
        extra={"role": user.user_roles[0].role.nom, "service_id": None},
    )


def _omvg_payload() -> dict[str, object]:
    return {
        "type_direction": "omvg",
        "date_apparition": "2026-06-12T10:30:00",
        "equipement_transport_id": 1,
        "cause_id": 1,
        "nature_id": 1,
        "siege_id": 1,
        "signalisation_id": 1,
    }


def _omvg_response(numero: int = 1) -> InterruptionTransportResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionTransportResponse(
        id=10,
        numero_interruption=numero,
        type_direction="omvg",
        statut="en_cours",
        service_id=None,
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
        tension_kv=None,
        equipement_transport_id=1,
        source_transport_id=None,
        puissance_transit_mw=None,
        energie_non_fournie_mwh=None,
        created_by_id=2,
        created_at=now,
        updated_at=now,
    )


async def test_dispatcher_create_omvg_returns_201(client: AsyncClient) -> None:
    user = _make_dispatcher()

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_transport_service.create",
        new_callable=AsyncMock,
        return_value=_omvg_response(numero=1),
    ) as mock_create:
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_omvg_payload(),
            headers=_auth_headers(_token(user)),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["type_direction"] == "omvg"
    assert body["data"]["statut"] == "en_cours"
    assert body["data"]["numero_interruption"] == 1
    mock_create.assert_awaited_once()


async def test_list_filter_omvg_returns_omvg_items(client: AsyncClient) -> None:
    user = _make_dispatcher()
    paginated = PaginatedResponse(
        items=[_omvg_response()],
        total=1,
        page=1,
        page_size=20,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_transport_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/transport?type_direction=omvg",
            headers=_auth_headers(_token(user)),
        )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["type_direction"] == "omvg"
    assert mock_list.await_args.kwargs["type_direction"] == "omvg"


async def test_next_numero_independent_per_type_direction() -> None:
    """Numérotation séquentielle distincte transport vs omvg (même année)."""
    session = AsyncMock()
    mock_result = MagicMock()

    mock_result.scalar_one.return_value = 5
    session.execute = AsyncMock(return_value=mock_result)
    transport_num = await next_numero_interruption(
        session, year=2026, type_direction="transport"
    )
    assert transport_num == 6

    mock_result.scalar_one.return_value = 2
    omvg_num = await next_numero_interruption(session, year=2026, type_direction="omvg")
    assert omvg_num == 3

    assert session.execute.await_count == 2
