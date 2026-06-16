"""Tests d'intégration — indicateurs SAIFI / SAIDI (phase 5.4)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.indicateurs import SaifiIndicateurResponse, SaifiSaidiAggregateResponse, SaidiIndicateurResponse

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


def _make_user(user_id: int, role_name: str, perms: list[tuple[str, str]]) -> Utilisateur:
    role = _make_role(1, role_name, perms)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = None
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


def _saifi_aggregate() -> SaifiSaidiAggregateResponse:
    return SaifiSaidiAggregateResponse(
        niveau="national",
        scope_id=None,
        annee=2026,
        mois=6,
        saifi=0.02,
        saidi=0.0,
        nombre_interruptions=5,
        total_clients_reference=50000,
    )


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(1, "ADMIN_SAQS", [("indicateurs", "read")])


async def test_get_saifi_returns_200(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = SaifiIndicateurResponse(aggregate=_saifi_aggregate(), services=None)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.indicateurs_service.get_saifi",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.get(
            "/api/v1/indicateurs/saifi?annee=2026&mois=6",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["aggregate"]["saifi"] == 0.02


async def test_get_saidi_returns_200(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    aggregate = _saifi_aggregate()
    aggregate = aggregate.model_copy(update={"saidi": 1.5, "saifi": 0.0})
    payload = SaidiIndicateurResponse(aggregate=aggregate, services=None)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.indicateurs_service.get_saidi",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.get(
            "/api/v1/indicateurs/saidi?annee=2026&mois=6",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    assert response.json()["data"]["aggregate"]["saidi"] == 1.5


async def test_get_saifi_missing_mois_returns_422(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs):
        response = await client.get(
            "/api/v1/indicateurs/saifi?annee=2026",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 422
