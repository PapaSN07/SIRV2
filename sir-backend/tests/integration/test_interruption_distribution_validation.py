"""Tests d'intégration — validation interruption distribution (phase 3.6)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import InterruptionDistributionResponse

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
    scope: int = 1,
) -> Utilisateur:
    role = _make_role(1, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope
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
        extra={"role": role_name, "service_id": user.user_roles[0].scope_service_id},
    )


def _valide_response() -> InterruptionDistributionResponse:
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 30, 0)
    return InterruptionDistributionResponse(
        id=1,
        numero_interruption=42,
        type_direction="distribution",
        statut="valide",
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
        puissance_coupee_mw=5.0,
        localisation=None,
        observations=None,
        is_force_majeure=False,
        is_fugitive=False,
        created_by_id=1,
        created_at=apparition,
        updated_at=remise,
    )


_BCC_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "update"),
]

_SUPERVISEUR_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "validate"),
]

_ADMIN_SCR_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
    ("interruptions_distribution", "validate"),
]


async def test_superviseur_valide_cloturee_returns_200(client: AsyncClient) -> None:
    user = _make_user(1, "SUPERVISEUR", _SUPERVISEUR_PERMS)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.valider",
        new_callable=AsyncMock,
        return_value=_valide_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/valider",
            headers=_auth_headers(_token(user, "SUPERVISEUR")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["statut"] == "valide"


async def test_bcc_valider_returns_403(client: AsyncClient) -> None:
    user = _make_user(1, "BCC", _BCC_PERMS)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/valider",
            headers=_auth_headers(_token(user, "BCC")),
        )

    assert response.status_code == 403


async def test_valider_en_cours_returns_422(client: AsyncClient) -> None:
    user = _make_user(1, "SUPERVISEUR", _SUPERVISEUR_PERMS)

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
        "app.services.interruption_distribution_service.valider",
        side_effect=_reject,
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/valider",
            headers=_auth_headers(_token(user, "SUPERVISEUR")),
        )

    assert response.status_code == 422


async def test_admin_scr_valide_returns_200(client: AsyncClient) -> None:
    user = _make_user(2, "ADMIN_SCR", _ADMIN_SCR_PERMS, scope=1)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.interruption_distribution_service.valider",
        new_callable=AsyncMock,
        return_value=_valide_response(),
    ):
        response = await client.patch(
            "/api/v1/interruptions/distribution/1/valider",
            headers=_auth_headers(_token(user, "ADMIN_SCR")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["statut"] == "valide"
