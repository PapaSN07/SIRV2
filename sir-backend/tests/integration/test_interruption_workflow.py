"""Tests d'intégration — workflow interruption distribution (phase B)."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_workflow import (
    InterruptionWorkflowResponse,
    WorkflowEtapeResponse,
    WorkflowStepClients,
)

pytestmark = pytest.mark.asyncio

_BCC_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
]

_BRC_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "create"),
    ("interruptions_distribution", "update"),
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
    scope_service_id: int | None = 1,
    permissions: list[tuple[str, str]] | None = None,
) -> Utilisateur:
    role = _make_role(role_nom, role_id, permissions or _BCC_PERMS)
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


def _workflow_response() -> InterruptionWorkflowResponse:
    return InterruptionWorkflowResponse(
        interruption_id=1,
        etapes=[
            WorkflowEtapeResponse(
                etape_workflow_id=1,
                code="declenchement",
                libelle_etape_workflow="Déclenchement",
                ordre=1,
                etape_suivante_id=2,
                etat="terminee",
                workflow_id=10,
                date_debut=datetime(2026, 6, 19, 8, 0, 0),
                date_fin=datetime(2026, 6, 19, 8, 15, 0),
                duree_minutes=15,
            ),
            WorkflowEtapeResponse(
                etape_workflow_id=2,
                code="interpellation_pdm",
                libelle_etape_workflow="Interpellation PDM",
                ordre=2,
                etape_suivante_id=3,
                etat="active",
            ),
        ],
        clients=WorkflowStepClients(nombre_postes_impactes=2, nombre_clients_touches=120),
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(1, "bcc_user", "BCC", 1, scope_service_id=1)


@pytest.fixture
def brc_user() -> Utilisateur:
    return _make_user(2, "brc_user", "BRC", 2, scope_service_id=3, permissions=_BRC_PERMS)


async def test_bcc_get_workflow_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_workflow_service.get_workflow",
        new_callable=AsyncMock,
        return_value=_workflow_response(),
    ) as mock_get:
        response = await client.get(
            "/api/v1/interruptions/distribution/1/workflow",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["data"]["etapes"][0]["duree_minutes"] == 15
    assert body["data"]["etapes"][1]["etat"] == "active"
    assert body["data"]["clients"]["nombre_postes_impactes"] == 2
    mock_get.assert_awaited_once()


async def test_brc_get_workflow_returns_200(
    client: AsyncClient,
    brc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=brc_user), patch(
        "app.services.interruption_workflow_service.get_workflow",
        new_callable=AsyncMock,
        return_value=_workflow_response(),
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution/1/workflow",
            headers=_auth_headers(_token(brc_user)),
        )

    assert response.status_code == 200
    assert response.json()["data"]["interruption_id"] == 1


async def test_bcc_put_workflow_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_workflow_service.update_etape",
        new_callable=AsyncMock,
        return_value=_workflow_response(),
    ) as mock_put:
        response = await client.put(
            "/api/v1/interruptions/distribution/1/workflow/etapes/1",
            headers=_auth_headers(_token(bcc_user)),
            json={
                "date_debut": "2026-06-19T08:00:00",
                "date_fin": "2026-06-19T08:15:00",
            },
        )

    assert response.status_code == 200
    mock_put.assert_awaited_once()
    assert mock_put.await_args.args[2] == 1


async def test_brc_put_workflow_returns_200(
    client: AsyncClient,
    brc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=brc_user), patch(
        "app.services.interruption_workflow_service.update_etape",
        new_callable=AsyncMock,
        return_value=_workflow_response(),
    ) as mock_put:
        response = await client.put(
            "/api/v1/interruptions/distribution/1/workflow/etapes/2",
            headers=_auth_headers(_token(brc_user)),
            json={"observation": "PDM interpellé"},
        )

    assert response.status_code == 200
    mock_put.assert_awaited_once()
