"""Tests d'intégration — endpoints organisation géographique (phase 2.2)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Role, UserRole, Utilisateur
from app.schemas.geo import (
    AgenceResponse,
    DelegationResponse,
    RegionResponse,
    ServiceResponse,
)

pytestmark = pytest.mark.asyncio


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_bcc_user() -> Utilisateur:
    role = Role()
    role.id = 1
    role.nom = "BCC"
    role.description = "BCC"
    role.is_active = True
    role.role_permissions = []

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = 1
    ur.role_id = 1
    ur.scope_service_id = 1
    ur.role = role

    user = Utilisateur()
    user.id = 1
    user.login = "bcc_user"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = "bcc@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _token_for(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": "BCC", "service_id": 1},
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_bcc_user()


# Jeu cohérent pour la chaîne hiérarchique
REGIONS = [
    RegionResponse(id=1, code="REG-DKR", libelle="Dakar", is_active=True),
    RegionResponse(id=2, code="REG-THS", libelle="Thiès", is_active=True),
]
DELEGATIONS = [
    DelegationResponse(
        id=10, region_id=1, code="DEL-DKR-01", libelle="Délégation Dakar Centre", is_active=True
    ),
]
AGENCES = [
    AgenceResponse(
        id=100, delegation_id=10, code="AGC-DKR-01", libelle="Agence Dakar Plateau", is_active=True
    ),
]
SERVICES = [
    ServiceResponse(
        id=1000,
        agence_id=100,
        code="SVC-DKR-01",
        libelle="Service Distribution Plateau",
        is_active=True,
    ),
]


async def test_get_regions_returns_200_non_empty(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.services.geo_service.list_regions",
        new_callable=AsyncMock,
        return_value=REGIONS,
    ):
        response = await client.get(
            "/api/v1/geo/regions",
            headers=_auth_headers(_token_for(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert len(body["data"]) >= 1
    assert body["data"][0]["code"] == "REG-DKR"


async def test_get_delegations_with_valid_region_id_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.services.geo_service.list_delegations",
        new_callable=AsyncMock,
        return_value=DELEGATIONS,
    ):
        response = await client.get(
            "/api/v1/geo/delegations?region_id=1",
            headers=_auth_headers(_token_for(bcc_user)),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["region_id"] == 1


async def test_get_regions_without_token_returns_403(
    client: AsyncClient,
) -> None:
    """HTTPBearer renvoie 403 lorsque le header Authorization est absent."""
    response = await client.get("/api/v1/geo/regions")
    assert response.status_code == 403


async def test_geo_hierarchy_chain_is_coherent(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    """Vérifie la cohérence region → délégation → agence → service."""
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.services.geo_service.list_regions",
        new_callable=AsyncMock,
        return_value=REGIONS,
    ), patch(
        "app.services.geo_service.list_delegations",
        new_callable=AsyncMock,
        return_value=DELEGATIONS,
    ), patch(
        "app.services.geo_service.list_agences",
        new_callable=AsyncMock,
        return_value=AGENCES,
    ), patch(
        "app.services.geo_service.list_services",
        new_callable=AsyncMock,
        return_value=SERVICES,
    ):
        headers = _auth_headers(_token_for(bcc_user))

        regions_resp = await client.get("/api/v1/geo/regions", headers=headers)
        region_id = regions_resp.json()["data"][0]["id"]

        deleg_resp = await client.get(
            f"/api/v1/geo/delegations?region_id={region_id}", headers=headers
        )
        delegation = deleg_resp.json()["data"][0]
        assert delegation["region_id"] == region_id

        agences_resp = await client.get(
            f"/api/v1/geo/agences?delegation_id={delegation['id']}", headers=headers
        )
        agence = agences_resp.json()["data"][0]
        assert agence["delegation_id"] == delegation["id"]

        services_resp = await client.get(
            f"/api/v1/geo/services?agence_id={agence['id']}", headers=headers
        )
        service = services_resp.json()["data"][0]
        assert service["agence_id"] == agence["id"]
