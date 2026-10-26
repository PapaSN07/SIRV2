"""POST /interruptions/distribution/import-fis : contrôles de format et de taille."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from tests.integration.test_interruption_distribution_create import _DISTRIB_CREATE_PERMS, _make_user

pytestmark = pytest.mark.asyncio

URL = "/api/v1/interruptions/distribution/import-fis"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _headers(user) -> dict[str, str]:
    token = create_access_token(subject=str(user.id), jti=str(uuid.uuid4()))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bcc_user():
    return _make_user(10, "bcc", "BCC", 1, _DISTRIB_CREATE_PERMS, scope_service_id=1)


async def test_extension_non_excel_refusee(client: AsyncClient, bcc_user) -> None:
    with patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user):
        response = await client.post(URL, files={"file": ("fis.csv", b"a;b", "text/csv")}, headers=_headers(bcc_user))
    assert response.status_code == 415


async def test_fichier_trop_volumineux_refuse(client: AsyncClient, bcc_user) -> None:
    big = b"0" * (10 * 1024 * 1024 + 1)
    with (
        patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user),
        patch("app.services.fis_import_service.import_fis_file", new_callable=AsyncMock) as importer,
    ):
        response = await client.post(URL, files={"file": ("fis.xlsx", big, XLSX)}, headers=_headers(bcc_user))
    assert response.status_code == 413
    importer.assert_not_awaited()


async def test_import_transmet_l_utilisateur(client: AsyncClient, bcc_user) -> None:
    from app.services.fis_import_service import FisImportResult, FisImportStats

    with (
        patch("app.repositories.utilisateur_repository.get_by_id", return_value=bcc_user),
        patch(
            "app.services.fis_import_service.import_fis_file",
            new_callable=AsyncMock,
            return_value=FisImportResult(stats=FisImportStats()),
        ) as importer,
    ):
        response = await client.post(URL, files={"file": ("fis.xlsx", b"PK", XLSX)}, headers=_headers(bcc_user))
    assert response.status_code == 200
    assert importer.await_args.kwargs["current_user"] is bcc_user
