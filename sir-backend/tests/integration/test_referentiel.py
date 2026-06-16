"""Tests d'intégration — endpoints référentiels (phase 2.1)."""

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.referentiel import Cause
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.referentiel import ReferentielResponse
from app.services import referentiel_service

pytestmark = pytest.mark.asyncio


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_role(nom: str, role_id: int, permissions: list[tuple[str, str]] | None = None) -> Role:
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = nom
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(permissions or [], start=1):
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


def _make_user(user_id: int, login: str, role_nom: str, role_id: int) -> Utilisateur:
    role = _make_role(role_nom, role_id)
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


def _token_for(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom},
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1)


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(2, "admin_scr", "ADMIN_SCR", 2)


def _sample_cause() -> ReferentielResponse:
    return ReferentielResponse(
        id=1,
        code="C01",
        libelle="Defaut materiel",
        type_reseau="distribution",
        description=None,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# GET causes → 200 + liste paginée
# ---------------------------------------------------------------------------


async def test_get_causes_returns_200_paginated(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_cause()],
        total=1,
        page=1,
        page_size=20,
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.services.referentiel_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/referentiel/causes",
            headers=_auth_headers(_token_for(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["code"] == "C01"


# ---------------------------------------------------------------------------
# POST cause BCC → 403
# ---------------------------------------------------------------------------


async def test_post_cause_as_bcc_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ):
        response = await client.post(
            "/api/v1/referentiel/causes",
            headers=_auth_headers(_token_for(bcc_user)),
            json={
                "code": "C99",
                "libelle": "Test",
                "type_reseau": "distribution",
            },
        )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST cause Admin SCR → 201
# ---------------------------------------------------------------------------


async def test_post_cause_as_admin_scr_returns_201(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    created = _sample_cause()
    created.code = "C99"

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=admin_scr,
    ), patch(
        "app.services.referentiel_service.create_item",
        new_callable=AsyncMock,
        return_value=created,
    ):
        response = await client.post(
            "/api/v1/referentiel/causes",
            headers=_auth_headers(_token_for(admin_scr)),
            json={
                "code": "C99",
                "libelle": "Nouvelle cause",
                "type_reseau": "distribution",
            },
        )

    assert response.status_code == 201
    assert response.json()["data"]["code"] == "C99"


# ---------------------------------------------------------------------------
# Filtre type_reseau=distribution
# ---------------------------------------------------------------------------


async def test_get_causes_filter_type_reseau_distribution(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    paginated = PaginatedResponse(
        items=[_sample_cause()],
        total=1,
        page=1,
        page_size=20,
    )

    with patch(
        "app.repositories.utilisateur_repository.get_by_id",
        return_value=bcc_user,
    ), patch(
        "app.services.referentiel_service.list_items",
        new_callable=AsyncMock,
        return_value=paginated,
    ) as mock_list:
        response = await client.get(
            "/api/v1/referentiel/causes?type_reseau=distribution",
            headers=_auth_headers(_token_for(bcc_user)),
        )

    assert response.status_code == 200
    mock_list.assert_awaited_once()
    # list_items(db, redis, resource, page, page_size, type_reseau)
    assert mock_list.call_args.args[5] == "distribution"
    for item in response.json()["data"]["items"]:
        assert item["type_reseau"] == "distribution"


# ---------------------------------------------------------------------------
# Modification → cache invalidé
# ---------------------------------------------------------------------------


async def test_update_bumps_cache_version(
    fake_redis: Any,
    admin_scr: Utilisateur,
    mock_db: AsyncMock,
) -> None:
    cause = Cause()
    cause.id = 1
    cause.code = "C01"
    cause.libelle = "Avant"
    cause.type_reseau = "distribution"
    cause.is_active = True

    await fake_redis.set("referentiel:causes:version", "0")
    await fake_redis.set(
        "referentiel:causes:v0:all:1:20",
        json.dumps({"items": [], "total": 0, "page": 1, "page_size": 20}),
    )

    with patch(
        "app.repositories.referentiel_repository.get_by_id",
        new_callable=AsyncMock,
        side_effect=[cause, cause],
    ), patch(
        "app.repositories.referentiel_repository.get_by_code",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.repositories.referentiel_repository.update",
        new_callable=AsyncMock,
        return_value=cause,
    ), patch(
        "app.services.referentiel_service.log_audit",
        new_callable=AsyncMock,
    ):
        from app.schemas.referentiel import ReferentielUpdate

        await referentiel_service.update_item(
            mock_db,
            fake_redis,
            admin_scr,
            "causes",
            1,
            ReferentielUpdate(libelle="Apres"),
        )

    version = await fake_redis.get("referentiel:causes:version")
    assert version == "1"

    # Ancienne clé v0 toujours en Redis mais version courante est 1
    current_version = await referentiel_service._get_cache_version(fake_redis, "causes")
    assert current_version == 1
