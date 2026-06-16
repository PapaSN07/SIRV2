"""Tests d'intégration — liste interruptions distribution (phase 3.2)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.interruption_distribution import InterruptionDistributionResponse

pytestmark = pytest.mark.asyncio

_READ_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
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
    scope_service_id: int | None = 1,
) -> Utilisateur:
    role = _make_role(role_nom, role_id, _READ_PERMS)
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


def _sample_item(service_id: int = 1, statut: str = "en_cours") -> InterruptionDistributionResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionDistributionResponse(
        id=1,
        numero_interruption=42,
        type_direction="distribution",
        statut=statut,  # type: ignore[arg-type]
        service_id=service_id,
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
    return _make_user(1, "bcc_user", "BCC", 1, scope_service_id=1)


async def test_bcc_list_own_service_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_item(service_id=1)],
        total=1,
        page=1,
        page_size=20,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/distribution",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["service_id"] == 1
    mock_list.assert_awaited_once()


async def test_list_filter_statut_en_cours(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_item(statut="en_cours")],
        total=1,
        page=1,
        page_size=20,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/distribution?statut=en_cours",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["statut"] == "en_cours"
    call_kwargs = mock_list.await_args.kwargs
    assert call_kwargs["statut"] == "en_cours"


async def test_list_filter_date_range(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(items=[], total=0, page=1, page_size=20)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/interruptions/distribution"
            "?date_debut=2026-06-01T00:00:00&date_fin=2026-06-30T23:59:59",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    call_kwargs = mock_list.await_args.kwargs
    assert call_kwargs["date_debut"] is not None
    assert call_kwargs["date_fin"] is not None


async def test_list_pagination_fields(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_item()],
        total=25,
        page=2,
        page_size=10,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution?page=2&page_size=10",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 25
    assert data["page"] == 2
    assert data["page_size"] == 10
