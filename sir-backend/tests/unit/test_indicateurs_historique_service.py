"""Tests unitaires — historique indicateurs (phase 5.5)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.services.indicateurs_service import _iter_months_back, get_historique


def test_iter_months_back_returns_chronological_order() -> None:
    points = _iter_months_back(1, end=datetime(2026, 6, 15))
    assert len(points) == 12
    assert points[0] == (2025, 7)
    assert points[-1] == (2026, 6)
    assert points == sorted(points)


@pytest.mark.asyncio
async def test_get_historique_invalid_type_raises_422() -> None:
    db = AsyncMock()
    redis = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await get_historique(
            db,
            redis,
            AsyncMock(user_roles=[]),
            indicateur_type="bad",
            annees=1,
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_get_historique_fin_termine_la_serie_au_mois_choisi() -> None:
    """Tableau de bord sur une période passée : la courbe se termine au mois choisi."""
    from unittest.mock import patch

    from app.services import indicateurs_service as svc

    with patch.object(svc, "_resolve_scope") as resolve, patch.object(
        svc, "_load_service_ids", new=AsyncMock(return_value=[1])
    ), patch.object(svc, "_historique_valeur_for_month", new=AsyncMock(return_value=1.0)):
        resolve.return_value = MagicMock(niveau="service", scope_id=None)
        result = await get_historique(
            AsyncMock(), AsyncMock(), AsyncMock(user_roles=[]),
            indicateur_type="end", annees=1, fin="2024-03",
        )
    keys = [(p.annee, p.mois) for p in result.points]
    assert keys[0] == (2023, 4)
    assert keys[-1] == (2024, 3)


@pytest.mark.asyncio
async def test_get_historique_fin_invalide_422() -> None:
    from unittest.mock import patch

    from app.services import indicateurs_service as svc

    with patch.object(svc, "_resolve_scope"), pytest.raises(HTTPException) as exc_info:
        await get_historique(
            AsyncMock(), AsyncMock(), AsyncMock(user_roles=[]),
            indicateur_type="saifi", annees=1, fin="2024-13",
        )
    assert exc_info.value.status_code == 422
