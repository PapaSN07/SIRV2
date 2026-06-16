"""Tests unitaires — saifi_saidi_service (phase 5.1)."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.indicateurs import SaifiSaidi
from app.models.interruptions import Interruption, PosteInterruption
from app.services.saifi_saidi_service import (
    aggregate_saifi_saidi_weighted,
    calcul_saifi,
    calcul_saidi,
    calculer_et_persister_saifi_saidi,
    compute_period_totals,
    sum_clients_interrompus,
)

def test_calcul_saifi_basic() -> None:
    assert calcul_saifi(1000, 50000) == Decimal("0.02")


def test_calcul_saifi_zero_denominator() -> None:
    assert calcul_saifi(1000, 0) == Decimal("0")


def test_calcul_saidi_basic() -> None:
    assert calcul_saidi(50000, 50000) == Decimal("1")


def test_sum_clients_interrompus() -> None:
    link1 = PosteInterruption()
    link1.nombre_clients_touches = 100
    link2 = PosteInterruption()
    link2.nombre_clients_touches = 50

    interruption = Interruption()
    interruption.postes_interrompus = [link1, link2]

    assert sum_clients_interrompus(interruption) == 150


def test_compute_period_totals_excludes_force_majeure() -> None:
    link = PosteInterruption()
    link.nombre_clients_touches = 200

    normal = Interruption()
    normal.is_force_majeure = False
    normal.duree_minutes = 60
    normal.postes_interrompus = [link]

    fm = Interruption()
    fm.is_force_majeure = True
    fm.duree_minutes = 120
    fm.postes_interrompus = [PosteInterruption(nombre_clients_touches=999)]

    clients, minutes, count = compute_period_totals([normal, fm])
    assert clients == 200
    assert minutes == 200 * 60
    assert count == 1


def test_aggregate_saifi_saidi_weighted() -> None:
    r1 = SaifiSaidi()
    r1.saifi = 0.02
    r1.saidi = 1.5
    r1.total_clients_reference = 10000
    r1.nombre_interruptions = 2

    r2 = SaifiSaidi()
    r2.saifi = 0.04
    r2.saidi = 2.0
    r2.total_clients_reference = 5000
    r2.nombre_interruptions = 1

    saifi, saidi, count, total_clients = aggregate_saifi_saidi_weighted([r1, r2])
    assert total_clients == 15000
    assert count == 3
    expected_saifi = (Decimal("0.02") * 10000 + Decimal("0.04") * 5000) / 15000
    assert saifi == expected_saifi


@pytest.mark.asyncio
async def test_calculer_et_persister_skips_non_distribution() -> None:
    db = AsyncMock()
    with patch(
        "app.services.saifi_saidi_service.repo.get_interruption_for_saifi_saidi",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await calculer_et_persister_saifi_saidi(db, 99)

    assert result["status"] == "skipped_not_distribution"


@pytest.mark.asyncio
async def test_calculer_et_persister_calculates_and_invalidates_cache() -> None:
    db = AsyncMock()
    interruption = Interruption()
    interruption.id = 1
    interruption.statut = "valide"
    interruption.service_id = 5
    interruption.date_apparition = datetime(2026, 6, 12, 10, 0, 0)
    interruption.is_force_majeure = False
    interruption.postes_interrompus = []

    record = SaifiSaidi()
    record.service_id = 5
    record.annee = 2026
    record.mois = 6
    record.saifi = 0.0
    record.saidi = 0.0
    record.nombre_interruptions = 0
    record.total_clients_reference = 50000

    with patch(
        "app.services.saifi_saidi_service.repo.get_interruption_for_saifi_saidi",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.saifi_saidi_service.recalculate_service_period",
        new_callable=AsyncMock,
        return_value=record,
    ), patch(
        "app.services.saifi_saidi_service.repo.get_region_id_for_service",
        new_callable=AsyncMock,
        return_value=2,
    ), patch(
        "app.services.saifi_saidi_service.invalidate_indicateurs_cache",
    ) as mock_invalidate:
        result = await calculer_et_persister_saifi_saidi(db, 1)

    assert result["status"] == "calculated"
    assert result["saifi"] == 0.0
    assert result["region_id"] == 2
    mock_invalidate.assert_called_once()
