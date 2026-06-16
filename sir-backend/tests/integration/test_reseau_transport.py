"""Tests d'intégration — réseau transport HTB (phase 2.4)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.reseau_transport import EquipementTransportResponse

pytestmark = pytest.mark.asyncio


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(user_id: int, login: str, role_nom: str, role_id: int) -> Utilisateur:
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
        extra={"role": user.user_roles[0].role.nom},
    )


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(1, "dispatcher", "DISPATCHER", 1)


@pytest.fixture
def admin_dispatching() -> Utilisateur:
    return _make_user(2, "admin_dispatch", "ADMIN_DISPATCHING", 2)


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(3, "admin_scr", "ADMIN_SCR", 3)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(4, "bcc_user", "BCC", 4)


def _equipement(item_id: int = 1) -> EquipementTransportResponse:
    return EquipementTransportResponse(
        id=item_id,
        code="LHTB-01",
        libelle="Ligne HTB Dakar",
        type_equipement="ligne",
        tension_kv=225.0,
        puissance_mva=100.0,
        is_active=True,
    )


async def test_dispatcher_get_equipements_returns_200(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    paginated = PaginatedResponse(items=[_equipement()], total=1, page=1, page_size=20)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.reseau_transport_service.list_resources",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/reseau/transport/equipements-transport",
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["code"] == "LHTB-01"


async def test_admin_dispatching_post_equipement_returns_201(
    client: AsyncClient,
    admin_dispatching: Utilisateur,
) -> None:
    created = _equipement(item_id=10)
    created.code = "LHTB-NEW"

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=admin_dispatching,
    ), patch(
        "app.services.reseau_transport_service.create_resource",
        new_callable=AsyncMock,
        return_value=created,
    ):
        response = await client.post(
            "/api/v1/reseau/transport/equipements-transport",
            headers=_auth_headers(_token(admin_dispatching)),
            json={
                "code": "LHTB-NEW",
                "libelle": "Nouvelle ligne",
                "type_equipement": "ligne",
                "tension_kv": 225.0,
            },
        )

    assert response.status_code == 201
    assert response.json()["data"]["code"] == "LHTB-NEW"


async def test_admin_scr_get_transport_returns_403(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_scr):
        response = await client.get(
            "/api/v1/reseau/transport/equipements-transport",
            headers=_auth_headers(_token(admin_scr)),
        )

    assert response.status_code == 403


async def test_bcc_get_transport_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.get(
            "/api/v1/reseau/transport/equipements-transport",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403
