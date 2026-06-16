"""Tests d'intégration — top feeders par END (phase 5.6)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.indicateurs import TopFeederItemResponse, TopFeedersResponse

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


def _top_feeders(limit: int = 10) -> TopFeedersResponse:
    items = [
        TopFeederItemResponse(
            feeder_id=1,
            code="FD-1",
            libelle="Feeder Alpha",
            service_id=1,
            end_mwh=15.0,
            nombre_interruptions=3,
        ),
        TopFeederItemResponse(
            feeder_id=2,
            code="FD-2",
            libelle="Feeder Beta",
            service_id=1,
            end_mwh=10.0,
            nombre_interruptions=2,
        ),
        TopFeederItemResponse(
            feeder_id=3,
            code="FD-3",
            libelle="Feeder Gamma",
            service_id=2,
            end_mwh=5.0,
            nombre_interruptions=1,
        ),
    ]
    return TopFeedersResponse(
        niveau="national",
        scope_id=None,
        annee=2026,
        mois=6,
        limit=limit,
        items=items[:limit],
    )


@pytest.fixture
def admin_saqs() -> Utilisateur:
    return _make_user(1, "ADMIN_SAQS", [("indicateurs", "read")])


async def test_get_top_feeders_returns_sorted_desc(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = _top_feeders(limit=10)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.indicateurs_service.get_top_feeders",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = await client.get(
            "/api/v1/indicateurs/top-feeders?periode=2026-06",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    end_values = [item["end_mwh"] for item in items]
    assert end_values == sorted(end_values, reverse=True)


async def test_get_top_feeders_limit_5(
    client: AsyncClient,
    admin_saqs: Utilisateur,
) -> None:
    payload = _top_feeders(limit=5)

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=admin_saqs), patch(
        "app.services.indicateurs_service.get_top_feeders",
        new_callable=AsyncMock,
        return_value=payload,
    ) as mock_top:
        response = await client.get(
            "/api/v1/indicateurs/top-feeders?periode=2026-06&limit=5",
            headers=_auth_headers(_token(admin_saqs, "ADMIN_SAQS")),
        )

    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) <= 5
    mock_top.assert_awaited_once()
    assert mock_top.await_args.kwargs["limit"] == 5
