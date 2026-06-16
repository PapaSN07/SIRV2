"""Tests unitaires — end_service (phase 3.8)."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Nature, TypeEnd
from app.models.reseau import Poste
from app.services.end_service import (
    calcul_end,
    compute_end_for_interruption,
    resolve_puissance_coupee_mw,
    calculer_et_persister_end,
)


def test_calcul_end_basic() -> None:
    assert calcul_end(5.0, 2.0) == Decimal("10.0")


def test_calcul_end_force_majeure_zero() -> None:
    assert calcul_end(5.0, 2.0, is_force_majeure=True) == Decimal("0")


def test_calcul_end_with_coefficient() -> None:
    assert calcul_end(5.0, 2.0, coefficient=Decimal("0.5")) == Decimal("5.0")


def test_resolve_puissance_from_interruption_field() -> None:
    interruption = Interruption()
    interruption.puissance_coupee_mw = 3.5
    interruption.postes_interrompus = []
    assert resolve_puissance_coupee_mw(interruption) == Decimal("3.5")


def test_resolve_puissance_from_postes_kva() -> None:
    poste = Poste()
    poste.puissance_kva = 500.0

    link = PosteInterruption()
    link.poste = poste

    interruption = Interruption()
    interruption.puissance_coupee_mw = None
    interruption.postes_interrompus = [link]

    assert resolve_puissance_coupee_mw(interruption) == Decimal("0.5")


def test_compute_end_for_interruption_force_majeure() -> None:
    interruption = Interruption()
    interruption.is_force_majeure = True
    interruption.puissance_coupee_mw = 10.0
    interruption.duree_minutes = 120
    interruption.postes_interrompus = []
    interruption.interruption_distribution = InterruptionDistribution()

    result = compute_end_for_interruption(interruption)
    assert result.valeur_mwh == Decimal("0")
    assert result.est_force_majeure is True


def test_compute_end_for_interruption_programme() -> None:
    nature = Nature()
    nature.code = "INCIDENT"

    distribution = InterruptionDistribution()
    distribution.is_programme = True

    interruption = Interruption()
    interruption.is_force_majeure = False
    interruption.puissance_coupee_mw = 2.0
    interruption.duree_minutes = 60
    interruption.nature = nature
    interruption.postes_interrompus = []
    interruption.interruption_distribution = distribution

    result = compute_end_for_interruption(interruption)
    assert result.valeur_mwh == Decimal("2.0")


@pytest.mark.asyncio
async def test_calculer_et_persister_end_persists_and_invalidates_cache() -> None:
    apparition = datetime(2026, 6, 12, 10, 0, 0)
    remise = datetime(2026, 6, 12, 12, 0, 0)

    interruption = Interruption()
    interruption.id = 1
    interruption.statut = "cloture"
    interruption.service_id = 1
    interruption.date_apparition = apparition
    interruption.date_remise = remise
    interruption.duree_minutes = 120
    interruption.is_force_majeure = False
    interruption.puissance_coupee_mw = 5.0
    interruption.postes_interrompus = []
    interruption.interruption_distribution = InterruptionDistribution(is_programme=False)
    interruption.nature = None

    type_end = TypeEnd()
    type_end.id = 2
    type_end.code = "END_IMPUTABLE"

    db = AsyncMock()

    with patch(
        "app.services.end_service.repo.get_interruption_for_end",
        new_callable=AsyncMock,
        return_value=interruption,
    ), patch(
        "app.services.end_service.repo.get_type_end_by_code",
        new_callable=AsyncMock,
        return_value=type_end,
    ), patch(
        "app.services.end_service.repo.upsert_energie_nd",
        new_callable=AsyncMock,
    ) as upsert_mock, patch(
        "app.services.end_service.repo.mirror_end_mwh",
        new_callable=AsyncMock,
    ) as mirror_mock, patch(
        "app.services.end_service.repo.get_region_id_for_service",
        new_callable=AsyncMock,
        return_value=3,
    ), patch("app.services.end_service.invalidate_end_cache") as cache_mock:
        result = await calculer_et_persister_end(db, 1)

    assert result["status"] == "calculated"
    assert result["valeur_mwh"] == 10.0
    assert result["est_force_majeure"] is False
    assert result["type_end_id"] == 2
    assert result["region_id"] == 3

    upsert_mock.assert_awaited_once()
    upsert_kwargs = upsert_mock.await_args.kwargs
    assert upsert_kwargs["interruption_id"] == 1
    assert upsert_kwargs["valeur_mwh"] == 10.0
    assert upsert_kwargs["type_end_id"] == 2

    mirror_mock.assert_awaited_once_with(db, 1, 10.0)
    cache_mock.assert_called_once_with(3, remise)


@pytest.mark.asyncio
async def test_calculer_et_persister_end_not_clotured_raises() -> None:
    interruption = Interruption()
    interruption.id = 1
    interruption.statut = "en_cours"

    db = AsyncMock()
    with patch(
        "app.services.end_service.repo.get_interruption_for_end",
        new_callable=AsyncMock,
        return_value=interruption,
    ):
        with pytest.raises(ValueError, match="non clôturée"):
            await calculer_et_persister_end(db, 1)
