"""Export Excel / PDF de la liste filtrée."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.common import PaginatedResponse
from app.schemas.interruption_distribution import InterruptionDistributionResponse
from app.services import interruption_export_service as export

pytestmark = pytest.mark.asyncio


def _item(i: int) -> InterruptionDistributionResponse:
    t = datetime(2026, 10, 20, 8, 0)
    return InterruptionDistributionResponse(
        id=i, numero_interruption=26000 + i, type_direction="distribution", statut="valide",
        service_id=1, feeder_id=1, poste_source_id=1, date_apparition=t, date_remise=t,
        duree_minutes=45, cause_id=1, nature_id=1, siege_id=1, signalisation_id=1,
        puissance_coupee_mw=1.5, localisation=None, observations=None, is_force_majeure=False,
        is_fugitive=False, created_by_id=1, created_at=t, updated_at=t, end_mwh=1.25,
        service_libelle="DR Dakar 1", feeder_libelle="HANN 30kV", cause_libelle="Défaut câble",
    )


async def test_xlsx_et_pdf_non_vides() -> None:
    items = [_item(i) for i in range(30)]
    xlsx = export.construire_xlsx(items, "Octobre 2026")
    pdf = export.construire_pdf(items, "Octobre 2026")
    assert xlsx[:2] == b"PK" and len(xlsx) > 3000
    assert pdf[:4] == b"%PDF" and len(pdf) > 2000


async def test_export_refuse_au_dela_du_plafond() -> None:
    from app.services import interruption_distribution_service as svc

    trop = PaginatedResponse(items=[], total=export.MAX_LIGNES_EXPORT + 1, page=1, page_size=1)
    with patch.object(svc, "list_items", AsyncMock(return_value=trop)), pytest.raises(HTTPException) as exc:
        await svc.exporter_liste(AsyncMock(), object(), format="xlsx", filtres_libelle="x")
    assert exc.value.status_code == 422
