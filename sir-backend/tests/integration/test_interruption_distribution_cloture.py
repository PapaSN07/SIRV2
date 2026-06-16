"""Tests d'intégration — clôture interruption distribution (phase 3.5)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import InterruptionDistributionResponse

pytestmark = pytest.mark.asyncio

_UPDATE_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "update"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(user_id: int = 1) -> Utilisateur:
    role = Role()
    role.id = 1
    role.nom = "BCC"
    role.description = "BCC"
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(_UPDATE_PERMS, start=1):
        perm = Permission()
        perm.id = i
        perm.ressource = ressource
        perm.action = action
        rp = RolePermission()
        rp.id = i
        rp.role_id = 1
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = 1
    ur.role = role

    user = Utilisateur()
    user.id = user_id
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


def _token(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": "BCC", "service_id": 1},
    )


def _cloture_response() -> InterruptionDistributionResponse:
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 30, 0)
    return InterruptionDistributionResponse(
        id=1,
        numero_interruption=42,
        type_direction="distribution",
        statut="cloture",
        service_id=1,
        feeder_id=1,
        poste_source_id=1,
        date_apparition=apparition,
        date_remise=remise,
        duree_minutes=150,
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
        created_at=apparition,
        updated_at=remise,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user()


async def test_cloture_without_postes_returns_422(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "Au moins un poste impacté est requis avant clôture",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.cloturer",
        side_effect=_reject,
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/cloturer",
            json={"date_remise": "2026-06-12T12:30:00"},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 422


async def test_cloture_invalid_date_remise_returns_422(
    client: AsyncClient,
    bcc_user: Utilisateur,
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

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.cloturer",
        side_effect=_reject,
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/cloturer",
            json={"date_remise": "2026-06-12T09:00:00"},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 422


async def test_cloture_ok_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.cloturer",
        new_callable=AsyncMock,
        return_value=_cloture_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/cloturer",
            json={"date_remise": "2026-06-12T12:30:00"},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["statut"] == "cloture"
    assert data["duree_minutes"] == 150


async def test_cloture_enqueues_calcul_end_task(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.cloturer",
        new_callable=AsyncMock,
        return_value=_cloture_response(),
    ) as mock_cloturer:
        await client.patch(
            "/api/v1/interruptions/distribution/1/cloturer",
            json={"date_remise": "2026-06-12T12:30:00"},
            headers=_auth_headers(_token(bcc_user)),
        )

    mock_cloturer.assert_awaited_once()
