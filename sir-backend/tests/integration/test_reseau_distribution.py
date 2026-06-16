"""Tests d'intégration — réseau distribution (phase 2.3)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.reseau_distribution import FeederResponse

pytestmark = pytest.mark.asyncio


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(user_id: int, login: str, role_nom: str, role_id: int, scope: int | None) -> Utilisateur:
    role = Role()
    role.id = role_id
    role.nom = role_nom
    role.description = role_nom
    role.is_active = True
    role.role_permissions = []

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = role_id
    ur.scope_service_id = scope
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


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, scope=1)


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(2, "admin_scr", "ADMIN_SCR", 2, scope=None)


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(3, "dispatcher", "DISPATCHER", 3, scope=None)


def _feeder(service_id: int, feeder_id: int = 10) -> FeederResponse:
    return FeederResponse(
        id=feeder_id,
        code=f"FD-{feeder_id}",
        libelle=f"Feeder {feeder_id}",
        poste_source_id=1,
        service_id=service_id,
        tension_kv=30.0,
        puissance_installee_mva=10.0,
        is_active=True,
    )


async def test_bcc_get_feeders_own_service_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(items=[_feeder(service_id=1)], total=1, page=1, page_size=20)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.reseau_distribution_service.list_resources",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/reseau/feeders",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["items"][0]["service_id"] == 1


async def test_bcc_get_feeders_other_service_returns_empty_list(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    empty = PaginatedResponse(items=[], total=0, page=1, page_size=20)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.reseau_distribution_service.list_resources",
        new_callable=AsyncMock,
        return_value=empty,
    ) as mock_list:
        response = await client.get(
            "/api/v1/reseau/feeders?service_id=99",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0
    mock_list.assert_awaited_once()


async def test_admin_scr_post_feeder_returns_201(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    created = _feeder(service_id=1, feeder_id=20)
    created.code = "FD-NEW"

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_scr), patch(
        "app.services.reseau_distribution_service.create_resource",
        new_callable=AsyncMock,
        return_value=created,
    ):
        response = await client.post(
            "/api/v1/reseau/feeders",
            headers=_auth_headers(_token(admin_scr)),
            json={
                "code": "FD-NEW",
                "libelle": "Nouveau feeder",
                "poste_source_id": 1,
                "service_id": 1,
            },
        )

    assert response.status_code == 201
    assert response.json()["data"]["code"] == "FD-NEW"


async def test_dispatcher_post_feeder_returns_403(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher):
        response = await client.post(
            "/api/v1/reseau/feeders",
            headers=_auth_headers(_token(dispatcher)),
            json={
                "code": "FD-X",
                "libelle": "Tentative",
                "poste_source_id": 1,
                "service_id": 1,
            },
        )

    assert response.status_code == 403
