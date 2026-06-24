"""Tests d'intégration — détail interruption distribution (phase 3.3)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import (
    InterruptionDistributionDetailResponse,
    PosteImpacteResponse,
    UtilisateurSummaryResponse,
)

pytestmark = pytest.mark.asyncio

_READ_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
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
    for i, (ressource, action) in enumerate(_READ_PERMS, start=1):
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
    scope_service_id: int | None = 1,
) -> Utilisateur:
    role = _make_role(role_nom, role_id)
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


def _detail_response(service_id: int = 1) -> InterruptionDistributionDetailResponse:
    now = datetime(2026, 6, 12, 10, 30, 0)
    return InterruptionDistributionDetailResponse(
        id=1,
        numero_interruption=42,
        type_direction="distribution",
        statut="en_cours",
        service_id=service_id,
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
        created_by_id=1,
        created_at=now,
        updated_at=now,
        feeder_libelle="Feeder Plateau Nord",
        cause_libelle="Defaut materiel",
        nature_libelle="Incident",
        siege_libelle="Siège A",
        signalisation_libelle="Signal A",
        service_code="SVC-DKR-01",
        service_libelle="Service Plateau",
        region_libelle="Dakar",
        postes_impactes=[
            PosteImpacteResponse(
                poste_id=1,
                poste_code="PT-DKR-01",
                poste_libelle="Poste BT Plateau",
                nombre_clients_touches=50,
            )
        ],
        created_by=UtilisateurSummaryResponse(id=1, login="bcc_user", nom="Test", prenom="User"),
        validated_by=None,
        validated_by_id=None,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, scope_service_id=1)


async def test_get_detail_existing_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    detail = _detail_response()

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.get_item",
        new_callable=AsyncMock,
        return_value=detail,
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution/1",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["feeder_libelle"] == "Feeder Plateau Nord"
    assert body["data"]["region_libelle"] == "Dakar"
    assert body["data"]["service_libelle"] == "Service Plateau"
    assert body["data"]["cause_libelle"] == "Defaut materiel"
    assert body["data"]["postes_impactes"][0]["poste_code"] == "PT-DKR-01"
    assert body["data"]["created_by"]["login"] == "bcc_user"


async def test_bcc_get_other_service_returns_403(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _forbidden(*_args, **_kwargs):
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": None,
                "error": "Hors périmètre : service_id non autorisé",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.get_item",
        side_effect=_forbidden,
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution/99",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 403


async def test_get_detail_not_found_returns_404(
    client: AsyncClient,
    bcc_user: Utilisateur,
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

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.get_item",
        side_effect=_not_found,
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution/999",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 404
