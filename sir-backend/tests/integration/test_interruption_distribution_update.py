"""Tests d'intégration — modification interruption distribution (phase 3.4)."""

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


def _make_role(role_id: int) -> Role:
    role = Role()
    role.id = role_id
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
        rp.role_id = role_id
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps
    return role


def _make_bcc(user_id: int, scope: int = 1) -> Utilisateur:
    role = _make_role(1)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = f"bcc_{user_id}"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = f"bcc_{user_id}@senelec.sn"
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
        extra={"role": "BCC", "service_id": user.user_roles[0].scope_service_id},
    )


def _response() -> InterruptionDistributionResponse:
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
        cause_id=2,
        nature_id=1,
        siege_id=1,
        signalisation_id=1,
        puissance_coupee_mw=5.0,
        localisation="Plateau",
        observations="Mise à jour",
        is_force_majeure=False,
        is_fugitive=False,
        created_by_id=1,
        created_at=now,
        updated_at=now,
    )


async def test_creator_put_returns_200(client: AsyncClient) -> None:
    user = _make_bcc(user_id=1)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.update",
        new_callable=AsyncMock,
        return_value=_response(),
    ):
        response = await client.put(
            "/api/v1/interruptions/distribution/1",
            json={"observations": "Mise à jour", "puissance_coupee_mw": 5.0},
            headers=_auth_headers(_token(user)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["observations"] == "Mise à jour"


async def test_other_bcc_put_returns_403(client: AsyncClient) -> None:
    user = _make_bcc(user_id=2)

    from fastapi import HTTPException

    async def _forbidden(*_args, **_kwargs):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": None,
                "error": "Seul le créateur ou Admin SCR peut modifier cette interruption",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.update",
        side_effect=_forbidden,
    ):
        response = await client.put(
            "/api/v1/interruptions/distribution/1",
            json={"observations": "Tentative"},
            headers=_auth_headers(_token(user)),
        )

    assert response.status_code == 403


async def test_put_cloture_returns_422(client: AsyncClient) -> None:
    user = _make_bcc(user_id=1)

    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "Modification autorisée uniquement pour une interruption en_cours",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.update",
        side_effect=_reject,
    ):
        response = await client.put(
            "/api/v1/interruptions/distribution/1",
            json={"observations": "Trop tard"},
            headers=_auth_headers(_token(user)),
        )

    assert response.status_code == 422


async def test_update_calls_audit_log(client: AsyncClient) -> None:
    user = _make_bcc(user_id=1)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.update",
        new_callable=AsyncMock,
        return_value=_response(),
    ) as mock_update:
        await client.put(
            "/api/v1/interruptions/distribution/1",
            json={"observations": "Audit test"},
            headers=_auth_headers(_token(user)),
        )

    mock_update.assert_awaited_once()
