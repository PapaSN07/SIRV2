"""Tests d'intégration — liste interruptions transport (phase 4.2)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_transport import InterruptionTransportResponse

pytestmark = pytest.mark.asyncio

_TRANSPORT_READ_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "create"),
    ("interruptions_transport", "update"),
]

_SAQS_READ_PERMS = [
    ("interruptions_transport", "read"),
]

_DISTRIB_READ_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
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
) -> Utilisateur:
    role = _make_role(role_nom, role_id, permissions)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role_id
    ur.scope_service_id = None
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
        extra={"role": user.user_roles[0].role.nom, "service_id": None},
    )


def _sample_item(statut: str = "en_cours") -> InterruptionTransportResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionTransportResponse(
        id=1,
        numero_interruption=7,
        type_direction="transport",
        statut=statut,  # type: ignore[arg-type]
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
        tension_kv=225.0,
        equipement_transport_id=1,
        source_transport_id=1,
        puissance_transit_mw=150.0,
        energie_non_fournie_mwh=None,
        created_by_id=2,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(2, "dispatcher", "DISPATCHER", 2, _TRANSPORT_READ_PERMS)


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(5, "admin_saqs", "ADMIN_SAQS", 5, _SAQS_READ_PERMS)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, _DISTRIB_READ_PERMS)


async def test_dispatcher_list_returns_200(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_item()],
        total=1,
        page=1,
        page_size=20,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/transport",
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["type_direction"] == "transport"
    mock_list.assert_awaited_once()


async def test_admin_saqs_list_returns_200(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_item()],
        total=1,
        page=1,
        page_size=20,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.interruption_transport_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/interruptions/transport",
            headers=_auth_headers(_token(admin_saqs)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["equipement_transport_id"] == 1


async def test_bcc_get_transport_list_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.get(
            "/api/v1/interruptions/transport",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403


async def test_list_filter_type_direction(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    paginated = PaginatedResponse(items=[], total=0, page=1, page_size=20)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/transport?type_direction=omvg",
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 200
    assert mock_list.await_args.kwargs["type_direction"] == "omvg"
