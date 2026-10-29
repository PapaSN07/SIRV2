"""END calculée immédiatement à la clôture (puissance × durée), repli sur le worker."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import end_service

pytestmark = pytest.mark.asyncio


def _db() -> MagicMock:
    db = MagicMock()

    @asynccontextmanager
    async def nested():
        yield

    db.begin_nested = nested
    return db


async def test_end_calculee_a_la_cloture() -> None:
    with patch.object(end_service, "calculer_et_persister_end", AsyncMock(return_value={"valeur_mwh": 2.5})):
        assert await end_service.calculer_a_la_cloture(_db(), 7) == 2.5


async def test_echec_repli_sur_le_worker() -> None:
    with patch.object(end_service, "calculer_et_persister_end", AsyncMock(side_effect=ValueError("dates"))):
        assert await end_service.calculer_a_la_cloture(_db(), 7) is None


def test_formule_puissance_par_duree() -> None:
    assert float(end_service.calcul_end(2.0, 1.5)) == 3.0
    assert float(end_service.calcul_end(2.0, 1.5, is_force_majeure=True)) == 0.0
