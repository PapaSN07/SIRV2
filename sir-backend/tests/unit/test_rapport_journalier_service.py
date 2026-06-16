"""Tests unitaires — collecte rapport journalier (phase 6.1)."""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.rapport_journalier_repository import JournalierFeederRow, JournalierInterruptionRow
from app.services import rapport_journalier_service as svc

pytestmark = pytest.mark.asyncio


async def test_collect_journalier_data_aggregates_end() -> None:
    report_date = date(2026, 6, 12)
    interruptions = [
        JournalierInterruptionRow(
            id=1,
            numero_interruption=100,
            type_direction="distribution",
            statut="cloture",
            date_apparition=datetime(2026, 6, 12, 8, 0),
            date_remise=datetime(2026, 6, 12, 10, 0),
            feeder_code="F01",
            feeder_libelle="Feeder 1",
            end_mwh=1.5,
            nombre_clients=120,
            service_id=1,
            libelle_reseau="Feeder 1",
        ),
        JournalierInterruptionRow(
            id=2,
            numero_interruption=101,
            type_direction="distribution",
            statut="en_cours",
            date_apparition=datetime(2026, 6, 12, 14, 0),
            date_remise=None,
            feeder_code="F02",
            feeder_libelle="Feeder 2",
            end_mwh=2.0,
            nombre_clients=80,
            service_id=1,
            libelle_reseau="Feeder 2",
        ),
    ]
    feeders = [
        JournalierFeederRow(
            feeder_id=1,
            code="F01",
            libelle="Feeder 1",
            nombre_interruptions=1,
            end_mwh=1.5,
        )
    ]
    db = AsyncMock()

    with patch(
        "app.repositories.rapport_journalier_repository.list_interruptions_for_day",
        return_value=interruptions,
    ), patch(
        "app.repositories.rapport_journalier_repository.aggregate_feeders_for_day",
        return_value=feeders,
    ):
        result = await svc.collect_journalier_data(
            db,
            report_date=report_date,
            region_id=None,
            service_id=None,
            include_transport=False,
        )

    assert result.nombre_interruptions == 2
    assert result.end_cumulee_mwh == 3.5
    assert len(result.feeders) == 1
