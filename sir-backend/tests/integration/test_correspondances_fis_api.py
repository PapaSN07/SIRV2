"""API /api/v1/correspondances-fis : authentification, droits, délégation au service.

Lecture : `interruptions_distribution:read` (BCC compris, pour l'écran d'import).
Création / suppression : `require_role("ADMIN_SCR")` + contrôle du service (droits du Référentiel).
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from tests.integration.test_interruption_distribution_create import _DISTRIB_CREATE_PERMS, _make_user

pytestmark = pytest.mark.asyncio

URL = "/api/v1/correspondances-fis"
SVC = "app.services.correspondance_fis_service"
GET_USER = "app.repositories.utilisateur_repository.get_by_id"

_LECTURE = [("interruptions_distribution", "read")]


def _headers(user) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), jti=str(uuid.uuid4()))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bcc_user():
    return _make_user(10, "bcc", "BCC", 1, _DISTRIB_CREATE_PERMS, scope_service_id=1)


@pytest.fixture
def admin_scr():
    return _make_user(20, "scr", "ADMIN_SCR", 2, _DISTRIB_CREATE_PERMS + [("interruptions_distribution", "validate")])


@pytest.fixture
def admin_saqs():
    return _make_user(30, "saqs", "ADMIN_SAQS", 3, _LECTURE)


@pytest.fixture
def admin_dispatching():
    return _make_user(50, "adisp", "ADMIN_DISPATCHING", 5, [("interruptions_transport", "read")])


@pytest.fixture
def sans_droit():
    return _make_user(40, "dispatcher", "DISPATCHER", 4, [("interruptions_transport", "read")])


def _reponse(id_: int = 5):
    from app.schemas.correspondance_fis import CorrespondanceFisResponse

    return CorrespondanceFisResponse(
        id=id_,
        categorie="cause",
        libelle_fis="chute de météorite",
        referentiel_id=1,
        referentiel_code="FACT_EXO",
        referentiel_libelle="Facteurs exogènes",
        is_force_majeure=True,
        created_at=datetime(2026, 11, 26, 8, 0),
    )


BODY = {"categorie": "cause", "libelle_fis": "Chute de météorite", "referentiel_id": 1, "is_force_majeure": True}


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------


# Sans en-tête Authorization, HTTPBearer du projet répond 403 (cf. test_auth_endpoints.py) ;
# un jeton invalide est refusé en 401.


@pytest.mark.parametrize("methode", ["get", "post", "delete"])
async def test_sans_jeton_refuse(client: AsyncClient, methode: str) -> None:
    url = f"{URL}/5" if methode == "delete" else URL
    kwargs = {"json": BODY} if methode == "post" else {}
    response = await getattr(client, methode)(url, **kwargs)
    assert response.status_code in (401, 403)


async def test_jeton_invalide_401(client: AsyncClient) -> None:
    response = await client.get(URL, headers={"Authorization": "Bearer jeton-invalide"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------


async def test_liste_pour_un_bcc(client: AsyncClient, bcc_user) -> None:
    with (
        patch(GET_USER, return_value=bcc_user),
        patch(f"{SVC}.lister", new_callable=AsyncMock, return_value=[_reponse()]) as lister,
    ):
        response = await client.get(URL, headers=_headers(bcc_user))
    assert response.status_code == 200, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["data"][0]["libelle_fis"] == "chute de météorite"
    assert corps["data"][0]["referentiel_code"] == "FACT_EXO"
    lister.assert_awaited_once()


async def test_liste_filtree_par_categorie(client: AsyncClient, bcc_user) -> None:
    with (
        patch(GET_USER, return_value=bcc_user),
        patch(f"{SVC}.lister", new_callable=AsyncMock, return_value=[]) as lister,
    ):
        response = await client.get(URL + "?categorie=cause", headers=_headers(bcc_user))
    assert response.status_code == 200, response.text
    appel = lister.await_args
    categorie = appel.kwargs.get("categorie", appel.args[1] if len(appel.args) > 1 else None)
    assert categorie == "cause"


async def test_liste_sans_permission_distribution_403(client: AsyncClient, sans_droit) -> None:
    with (
        patch(GET_USER, return_value=sans_droit),
        patch(f"{SVC}.lister", new_callable=AsyncMock, return_value=[]) as lister,
    ):
        response = await client.get(URL, headers=_headers(sans_droit))
    assert response.status_code == 403
    lister.assert_not_awaited()


# ---------------------------------------------------------------------------
# Création
# ---------------------------------------------------------------------------


async def test_creation_par_admin_scr_201(client: AsyncClient, admin_scr) -> None:
    with (
        patch(GET_USER, return_value=admin_scr),
        patch(f"{SVC}.creer", new_callable=AsyncMock, return_value=_reponse()) as creer,
    ):
        response = await client.post(URL, json=BODY, headers=_headers(admin_scr))
    assert response.status_code == 201, response.text
    corps = response.json()
    assert corps["status"] == "success"
    assert corps["data"]["id"] == 5
    assert corps["data"]["is_force_majeure"] is True
    creer.assert_awaited_once()
    appel = creer.await_args
    utilisateur = appel.kwargs.get("current_user", appel.args[1] if len(appel.args) > 1 else None)
    assert utilisateur is admin_scr
    body = appel.kwargs.get("body", appel.args[2] if len(appel.args) > 2 else None)
    assert body.categorie == "cause" and body.referentiel_id == 1


@pytest.mark.parametrize("fixture", ["bcc_user", "admin_saqs", "admin_dispatching"])
async def test_creation_refusee_hors_admin_scr_403(client: AsyncClient, request, fixture: str) -> None:
    user = request.getfixturevalue(fixture)
    with (
        patch(GET_USER, return_value=user),
        patch(f"{SVC}.creer", new_callable=AsyncMock, return_value=_reponse()) as creer,
    ):
        response = await client.post(URL, json=BODY, headers=_headers(user))
    assert response.status_code == 403
    creer.assert_not_awaited()


# ---------------------------------------------------------------------------
# Suppression
# ---------------------------------------------------------------------------


async def test_suppression_par_admin_scr_200(client: AsyncClient, admin_scr) -> None:
    with (
        patch(GET_USER, return_value=admin_scr),
        patch(f"{SVC}.supprimer", new_callable=AsyncMock, return_value=None) as supprimer,
    ):
        response = await client.delete(f"{URL}/5", headers=_headers(admin_scr))
    assert response.status_code == 200, response.text
    supprimer.assert_awaited_once()
    appel = supprimer.await_args
    assert admin_scr in appel.args or appel.kwargs.get("current_user") is admin_scr
    assert 5 in appel.args or 5 in appel.kwargs.values()


async def test_suppression_refusee_pour_un_bcc_403(client: AsyncClient, bcc_user) -> None:
    with (
        patch(GET_USER, return_value=bcc_user),
        patch(f"{SVC}.supprimer", new_callable=AsyncMock, return_value=None) as supprimer,
    ):
        response = await client.delete(f"{URL}/5", headers=_headers(bcc_user))
    assert response.status_code == 403
    supprimer.assert_not_awaited()
