"""Tests d'intégration — postes impactés interruption distribution (phase 3.7)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.interruption_distribution import PosteImpacteResponse

pytestmark = pytest.mark.asyncio

_READ_UPDATE_PERMS = [
    ("interruptions_distribution", "read"),
    ("interruptions_distribution", "update"),
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
    for i, (ressource, action) in enumerate(_READ_UPDATE_PERMS, start=1):
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


def _make_user(user_id: int = 1) -> Utilisateur:
    role = _make_role("BCC", 1)
    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = 1
    ur.role = role

    user = Utilisateur()
    user.id = user_id
    user.login = "bcc_user"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = "bcc_user@senelec.sn"
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
        extra={"role": "BCC", "service_id": 1},
    )


def _poste_response() -> PosteImpacteResponse:
    return PosteImpacteResponse(
        poste_id=1,
        poste_code="PT-DKR-01",
        poste_libelle="Poste BT Plateau",
        nombre_clients_touches=50,
    )


@pytest.fixture
def bcc_user() -> Utilisateur:
    return _make_user()


async def test_post_poste_en_cours_returns_201(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.add_poste",
        new_callable=AsyncMock,
        return_value=_poste_response(),
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes",
            json={"poste_id": 1, "nombre_clients_touches": 50},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["poste_code"] == "PT-DKR-01"


async def test_post_poste_cloturee_returns_422(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from fastapi import HTTPException

    async def _reject(*_args, **_kwargs):
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "data": None,
                "error": "Modification autorisée uniquement pour une interruption en_cours",
            },
        )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.add_poste",
        side_effect=_reject,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes",
            json={"poste_id": 1},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 422


async def test_delete_poste_returns_204(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.remove_poste",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await client.delete(
            "/api/v1/interruptions/distribution/1/postes/1",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 204


async def test_get_postes_returns_200(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.list_postes",
        new_callable=AsyncMock,
        return_value=[_poste_response()],
    ):
        response = await client.get(
            "/api/v1/interruptions/distribution/1/postes",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert len(body["data"]) == 1


async def test_post_postes_from_feeder_returns_201(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from app.schemas.interruption_distribution import PosteImpacteBulkResponse

    bulk = PosteImpacteBulkResponse(
        added_count=2,
        skipped_count=1,
        items=[_poste_response()],
    )
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.add_postes_from_feeder",
        new_callable=AsyncMock,
        return_value=bulk,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes/from-feeder",
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 201
    assert response.json()["data"]["added_count"] == 2


async def test_post_postes_from_sig_troncon_returns_201(
    client: AsyncClient,
    bcc_user: Utilisateur,
) -> None:
    from app.schemas.interruption_distribution import PosteImpacteBulkResponse

    bulk = PosteImpacteBulkResponse(added_count=1, skipped_count=0, items=[_poste_response()])
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user), patch(
        "app.services.interruption_distribution_service.add_postes_from_sig_troncon",
        new_callable=AsyncMock,
        return_value=bulk,
    ):
        response = await client.post(
            "/api/v1/interruptions/distribution/1/postes/from-sig-troncon",
            json={"troncon_sig_id": 5},
            headers=_auth_headers(_token(bcc_user)),
        )

    assert response.status_code == 201
    assert response.json()["data"]["added_count"] == 1
