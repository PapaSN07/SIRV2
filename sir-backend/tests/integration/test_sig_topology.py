"""Tests d'intégration — API topologie SIG."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur
from app.schemas.common import PaginatedResponse
from app.schemas.sig import TronconSigChaineResponse, TronconSigResponse

pytestmark = pytest.mark.asyncio

_READ_PERMS = [
    ("interruptions_distribution", "read"),
]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user() -> Utilisateur:
    role = Role()
    role.id = 1
    role.nom = "BCC"
    role.description = "BCC"
    role.is_active = True
    rps: list[RolePermission] = []
    for i, (ressource, action) in enumerate(_READ_PERMS, start=1):
        perm = Permission()
        perm.id = i
        perm.ressource = ressource
        perm.action = action
        rp = RolePermission()
        rp.id = i
        rp.role_id = 1
        rp.permission_id = i
        rp.role = role
        rp.permission = perm
        rps.append(rp)
    role.role_permissions = rps

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = 1
    ur.role_id = 1
    ur.scope_service_id = 1
    ur.role = role

    user = Utilisateur()
    user.id = 1
    user.login = "bcc_user"
    user.password_hash = hash_password("MotDePasse123!")
    user.nom = "Test"
    user.prenom = "User"
    user.email = "bcc@senelec.sn"
    user.telephone = None
    user.is_active = True
    user.premiere_connexion = False
    user.user_roles = [ur]
    user.audit_logs = []
    ur.utilisateur = user
    return user


def _sample_troncon() -> TronconSigResponse:
    return TronconSigResponse(
        id=1,
        legacy_id=100,
        legacy_fid=5001,
        nom_feeder="FEEDER_A",
        feeder_id=1,
        nom_troncon="TR-001",
        nom_noeud_amont="PS_DAKAR",
        code_noeud_amont="N001",
        nom_noeud_aval="PIQ_12",
        code_noeud_aval="N002",
        tension_kv=30.0,
        longueur_m=120.5,
        date_chargement=None,
    )


async def test_list_troncons_sig_returns_200(client: AsyncClient) -> None:
    user = _make_user()
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": "BCC", "service_id": 1},
    )
    paginated = PaginatedResponse(
        items=[_sample_troncon()],
        total=1,
        page=1,
        page_size=50,
    )

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.sig_service.list_troncons_sig",
        new_callable=AsyncMock,
        return_value=paginated,
    ):
        response = await client.get(
            "/api/v1/reseau/sig/troncons?feeder_id=1",
            headers=_auth_headers(token),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["items"][0]["nom_troncon"] == "TR-001"


async def test_chaine_aval_returns_200(client: AsyncClient) -> None:
    user = _make_user()
    token = create_access_token(
        subject=str(user.id),
        jti=str(uuid.uuid4()),
        extra={"role": "BCC", "service_id": 1},
    )
    troncon = _sample_troncon()
    chain = TronconSigChaineResponse(troncon=troncon, chaine_aval=[])

    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=user), patch(
        "app.services.sig_service.get_chaine_aval",
        new_callable=AsyncMock,
        return_value=chain,
    ):
        response = await client.get(
            "/api/v1/reseau/sig/troncons/1/chaine-aval?limit=3",
            headers=_auth_headers(token),
        )

    assert response.status_code == 200
    assert response.json()["data"]["troncon"]["id"] == 1
