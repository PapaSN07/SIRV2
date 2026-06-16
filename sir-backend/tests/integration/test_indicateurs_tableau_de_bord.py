"""Tests d'intégration — tableau de bord indicateurs (phase 5.3)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.indicateurs import TableauDeBordResponse

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
    scope: int | None = None,
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


def _dashboard(niveau: str = "national", scope_id: int | None = None) -> TableauDeBordResponse:
    return TableauDeBordResponse(
        niveau=niveau,
        scope_id=scope_id,
        annee=2026,
        mois=6,
        end_mois=12.5,
        saifi=0.02,
        saidi=1.5,
        nb_interruptions_actives=2,
        nb_interruptions_mois=5,
    )


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(1, "ADMIN_SAQS", [("indicateurs", "read")], scope=None)


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user(2, "BCC", [("indicateurs", "read")], scope=1)


async def test_admin_saqs_tableau_de_bord_returns_5_kpis(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = _dashboard()

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.indicateurs_service.get_tableau_de_bord",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.get(
            "/api/v1/indicateurs/tableau-de-bord?periode=2026-06",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["end_mois"] == 12.5
    assert data["saifi"] == 0.02
    assert data["saidi"] == 1.5
    assert data["nb_interruptions_actives"] == 2
    assert data["nb_interruptions_mois"] == 5


async def test_bcc_tableau_de_bord_limited_to_service(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    payload = _dashboard(niveau="service", scope_id=1)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.indicateurs_service.get_tableau_de_bord",
        new_callable=AsyncMock,
        return_value=payload,
    ) as mock_dashboard:
        response = await client.get(
            "/api/v1/indicateurs/tableau-de-bord?annee=2026&mois=6",
            headers=_auth_headers(_token(bcc_user, "BCC")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["niveau"] == "service"
    assert response.json()["data"]["scope_id"] == 1
    mock_dashboard.assert_awaited_once()
