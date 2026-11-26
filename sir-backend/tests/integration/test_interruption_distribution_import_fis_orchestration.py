"""POST /interruptions/distribution/import-fis : la route passe par `fis_import_service.importer_fis`
(correspondances administrées + historique des statuts), avec l'utilisateur et `skip_existing`."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from tests.integration.test_interruption_distribution_create import _DISTRIB_CREATE_PERMS, _make_user

pytestmark = pytest.mark.asyncio

URL = "/api/v1/interruptions/distribution/import-fis"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IMPORTER = "app.services.fis_import_service.importer_fis"


def _headers(user) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), jti=str(uuid.uuid4()))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bcc_user():
    return _make_user(10, "bcc", "BCC", 1, _DISTRIB_CREATE_PERMS, scope_service_id=1)


def _resultat():
    from app.services.fis_import_service import FisImportResult, FisImportStats

    return FisImportResult(stats=FisImportStats(total_lignes=1, importees=1))


@pytest.mark.parametrize(("query", "attendu"), [("", True), ("?skip_existing=false", False)])
async def test_route_appelle_importer_fis(client: AsyncClient, bcc_user, mock_db, query: str, attendu: bool) -> None:
    with (
        patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user),
        patch(IMPORTER, new_callable=AsyncMock, return_value=_resultat()) as importer,
    ):
        response = await client.post(
            URL + query, files={"file": ("fis.xlsx", b"PK", XLSX)}, headers=_headers(bcc_user)
        )
    assert response.status_code == 200, response.text
    importer.assert_awaited_once()
    assert importer.await_args.args[1] == b"PK"
    assert importer.await_args.kwargs["current_user"] is bcc_user
    assert importer.await_args.kwargs["skip_existing"] is attendu
    assert response.json()["data"]["stats"]["importees"] == 1
    mock_db.commit.assert_awaited()


async def test_simulation_annule_tout_meme_l_historique(client: AsyncClient, bcc_user, mock_db) -> None:
    with (
        patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user),
        patch(IMPORTER, new_callable=AsyncMock, return_value=_resultat()) as importer,
    ):
        response = await client.post(
            URL + "?simulation=true", files={"file": ("fis.xlsx", b"PK", XLSX)}, headers=_headers(bcc_user)
        )
    assert response.status_code == 200, response.text
    importer.assert_awaited_once()
    mock_db.rollback.assert_awaited()
    mock_db.commit.assert_not_awaited()
