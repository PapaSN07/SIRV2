"""Tests unitaires — historique indicateurs (phase 5.5)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

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
