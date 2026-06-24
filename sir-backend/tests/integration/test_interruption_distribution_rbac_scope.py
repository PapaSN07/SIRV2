"""Tests d'intégration — périmètre RBAC BCC/BRC (service) distribution."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import (
    InterruptionDistributionResponse,
    PosteImpacteBulkResponse,
)

pytestmark = pytest.mark.asyncio

_BCC_WRITE_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
]

_BRC_WRITE_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
]

_READ_ONLY_PERMS = [
    ("interruptions_distribution", "read"),
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
    scope_service_id: int | None,
    permissions: list[tuple[str, str]],
) -> Utilisateur:
    role = _make_role(role_nom, role_id, permissions)
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


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, 1, _BCC_WRITE_PERMS)


@pytest.fixture
def brc_user() -> Utilisateur:
    return _make_user(2, "brc_user", "BRC", 2, 3, _BRC_WRITE_PERMS)


@pytest.fixture
def saqs_user() -> Utilisateur:
    return _make_user(3, "saqs_user", "ADMIN_SAQS", 3, None, _READ_ONLY_PERMS)


async def test_brc_create_with_write_permission_returns_201(
    client: AsyncClient,
    brc_user: Utilisateur,
) -> None:
    from datetime import datetime

    now = datetime(2026, 6, 12, 10, 30, 0)
    created = InterruptionDistributionResponse(
        id=99,
        numero_interruption=99,
        type_direction="distribution",
        statut="en_cours",
        service_id=10,
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
        created_by_id=2,
        created_at=now,
        updated_at=now,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=brc_user), patch(
        "app.services.interruption_distribution_service.create",
        new_callable=AsyncMock,
        return_value=created,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json={
                "date_apparition": "2026-06-12T10:30:00",
                "poste_source_id": 1,
                "feeder_id": 1,
                "cause_id": 1,
                "nature_id": 1,
                "siege_id": 1,
                "signalisation_id": 1,
            },
            headers=_auth_headers(_token(brc_user)),
        )

    assert response.status_code == 201


async def test_brc_create_without_write_permission_returns_403(
    client: AsyncClient,
) -> None:
    brc_readonly = _make_user(4, "brc_ro", "BRC", 4, 3, _READ_ONLY_PERMS)
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=brc_readonly):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json={
                "date_apparition": "2026-06-12T10:30:00",
                "poste_source_id": 1,
                "feeder_id": 1,
                "cause_id": 1,
                "nature_id": 1,
                "siege_id": 1,
                "signalisation_id": 1,
            },
            headers=_auth_headers(_token(brc_readonly)),
        )

    assert response.status_code == 403


async def test_brc_bulk_postes_from_feeder_allowed_with_update(
    client: AsyncClient,
    brc_user: Utilisateur,
) -> None:
    bulk = PosteImpacteBulkResponse(added_count=3, skipped_count=0, items=[])
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=brc_user), patch(
        "app.services.interruption_distribution_service.add_postes_from_feeder",
        new_callable=AsyncMock,
        return_value=bulk,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes/from-feeder",
            headers=_auth_headers(_token(brc_user)),
        )

    assert response.status_code == 201
    assert response.json()["data"]["added_count"] == 3


async def test_saqs_bulk_postes_returns_403(
    client: AsyncClient,
    saqs_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=saqs_user):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes/from-feeder",
            headers=_auth_headers(_token(saqs_user)),
        )

    assert response.status_code == 403


async def test_bcc_create_out_of_scope_returns_403_via_service(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=403,
            detail={"status": "error", "data": None, "error": "Hors périmètre : service_id non autorisé"},
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.create",
        side_effect=_reject,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution",
            json={
                "date_apparition": "2026-06-12T10:30:00",
                "poste_source_id": 1,
                "feeder_id": 99,
                "cause_id": 1,
                "nature_id": 1,
                "siege_id": 1,
                "signalisation_id": 1,
            },
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403
