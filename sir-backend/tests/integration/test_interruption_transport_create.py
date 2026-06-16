"""Tests d'intégration — création interruption transport (phase 4.1)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_transport import InterruptionTransportResponse

pytestmark = pytest.mark.asyncio

_DISTRIB_CREATE_PERMS = [
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "update"),
]

_TRANSPORT_CREATE_PERMS = [
    ("interruptions_transport", "create"),
    ("interruptions_transport", "read"),
    ("interruptions_transport", "update"),
]

_TRANSPORT_VALIDATE_PERMS = [
    ("interruptions_transport", "create"),
    ("interruptions_transport", "read"),
    ("interruptions_transport", "update"),
    ("interruptions_transport", "validate"),
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
    scope_service_id: int | None = None,
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


def _valid_payload() -> dict[str, object]:
    return {
        "date_apparition": "2026-06-12T10:30:00",
        "equipement_transport_id": 1,
        "cause_id": 1,
        "nature_id": 1,
        "siege_id": 1,
        "signalisation_id": 1,
    }


def _sample_response() -> InterruptionTransportResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionTransportResponse(
        id=1,
        numero_interruption=7,
        type_direction="transport",
        statut="en_cours",
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
        tension_kv=None,
        equipement_transport_id=1,
        source_transport_id=None,
        puissance_transit_mw=None,
        energie_non_fournie_mwh=None,
        created_by_id=2,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, _DISTRIB_CREATE_PERMS, scope_service_id=1)


@pytest.fixture
def admin_scr() -> Utilisateur:
    return _make_user(3, "admin_scr", "ADMIN_SCR", 3, _DISTRIB_CREATE_PERMS, scope_service_id=None)


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(2, "dispatcher", "DISPATCHER", 2, _TRANSPORT_CREATE_PERMS, scope_service_id=None)


@pytest.fixture
def admin_dispatching() -> Utilisateur:
    return _make_user(4, "admin_dispatching", "ADMIN_DISPATCHING", 4, _TRANSPORT_VALIDATE_PERMS, scope_service_id=None)


async def test_dispatcher_create_interruption_returns_201(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.create",
        new_callable=AsyncMock,
        return_value=_sample_response(),
    ):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_valid_payload(),
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["statut"] == "en_cours"
    assert body["data"]["numero_interruption"] == 7
    assert body["data"]["type_direction"] == "transport"


async def test_admin_dispatching_create_interruption_returns_201(
    client: AsyncClient,
    admin_dispatching: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_dispatching), patch(
        "app.services.interruption_transport_service.create",
        new_callable=AsyncMock,
        return_value=_sample_response(),
    ):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_valid_payload(),
            headers=_auth_headers(_token(admin_dispatching)),
        )

    assert response.status_code == 201
    assert response.json()["data"]["statut"] == "en_cours"


async def test_bcc_post_transport_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_valid_payload(),
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403


async def test_admin_scr_post_transport_returns_403(
    client: AsyncClient,
    admin_scr: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_scr):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_valid_payload(),
            headers=_auth_headers(_token(admin_scr)),
        )

    assert response.status_code == 403


async def test_create_missing_required_fields_returns_422(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json={"date_apparition": "2026-06-12T10:30:00"},
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 422


async def test_create_equipement_inactif_returns_422(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _raise_inactive(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "Équipement transport 1 introuvable ou inactif",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.create",
        side_effect=_raise_inactive,
    ):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json=_valid_payload(),
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 422


async def test_create_poste_ligne_incoherent_returns_422(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _raise_mismatch(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "poste_ligne_id incohérent avec equipement_transport_id",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.create",
        side_effect=_raise_mismatch,
    ):
        response = await client.post(
            "/api/v1/interruptions/transport",
            json={**_valid_payload(), "poste_ligne_id": 99},
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 422
