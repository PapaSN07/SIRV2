"""Tests d'intégration — détail interruption transport (phase 4.2)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_transport import (
    InterruptionTransportDetailResponse,
    UtilisateurSummaryResponse,
)

pytestmark = pytest.mark.asyncio

_TRANSPORT_READ_PERMS = [
    ("interruptions_transport", "read"),
    ("interruptions_transport", "create"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_role(nom: str, role_id: int) -> Role:
    role = Role()
    role.id = role_id
    role.nom = nom
    role.description = nom
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(_TRANSPORT_READ_PERMS, start=1):
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


def _token(user: Utilisateur) -> str:
    return create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": user.user_roles[0].role.nom, "service_id": None},
    )


def _detail_response() -> InterruptionTransportDetailResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionTransportDetailResponse(
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
        puissance_coupee_mw=50.0,
        localisation="Poste Yoff",
        observations=None,
        is_force_majeure=False,
        is_fugitive=False,
        tension_kv=225.0,
        equipement_transport_id=1,
        source_transport_id=1,
        puissance_transit_mw=150.0,
        energie_non_fournie_mwh=None,
        created_by_id=2,
        created_at=now,
        updated_at=now,
        equipement_libelle="Ligne HTB Yoff-Tivaouane",
        source_libelle="Centrale Cap des Biches",
        cause_libelle="Defaut materiel",
        nature_libelle="Incident",
        siege_libelle="Siège transport A",
        signalisation_libelle="Signal HTB A",
        created_by=UtilisateurSummaryResponse(
            id=2, login="dispatcher", nom="Test", prenom="User"
        ),
        validated_by=None,
        validated_by_id=None,
    )


@pytest.fixture
def dispatcher() -> Utilisateur:
    return _make_user(2, "dispatcher", "DISPATCHER", 2)


async def test_get_detail_existing_returns_200(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    detail = _detail_response()

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.get_item",
        new_callable=AsyncMock,
        return_value=detail,
    ):
        response = await client.get(
            "/api/v1/interruptions/transport/1",
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["equipement_libelle"] == "Ligne HTB Yoff-Tivaouane"
    assert body["data"]["puissance_transit_mw"] == 150.0
    assert body["data"]["created_by"]["login"] == "dispatcher"


async def test_get_detail_not_found_returns_404(
    client: AsyncClient,
    dispatcher: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _not_found(*_args, **_kwargs):
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "data": None,
                "error": "Interruption 999 introuvable",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=dispatcher), patch(
        "app.services.interruption_transport_service.get_item",
        side_effect=_not_found,
    ):
        response = await client.get(
            "/api/v1/interruptions/transport/999",
            headers=_auth_headers(_token(dispatcher)),
        )

    assert response.status_code == 404
