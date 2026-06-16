"""Tests unitaires — top feeders indicateurs (phase 5.6)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.indicateurs_repository import EndFeederRow
from app.services.indicateurs_service import get_top_feeders


@pytest.mark.asyncio
async def test_get_top_feeders_clamps_limit() -> None:
    db = AsyncMock()
    redis = AsyncMock()
    user = AsyncMock()
    scope = SimpleNamespace(
        niveau="national",
        scope_id=None,
        service_ids=[],
        cache_region_id=0,
    )

    rows = [
        EndFeederRow(1, "FD-1", "A", 1, 10.0, 1),
    ]

    async def _fake_get_or_load(_redis, _cr, _a, _m, _l, loader):
        return await loader()

    with patch(
        "app.services.indicateurs_service._resolve_scope",
        return_value=scope,
    ), patch(
        "app.services.indicateurs_service._load_service_ids",
        new_callable=AsyncMock,
        return_value=[1],
    ), patch(
        "app.services.indicateurs_service.repo.aggregate_end_by_feeders",
        new_callable=AsyncMock,
        return_value=rows,
    ) as mock_agg, patch(
        "app.services.indicateurs_service.get_or_load_top_feeders",
        side_effect=_fake_get_or_load,
    ):
        result = await get_top_feeders(
            db,
            redis,
            user,
            annee=2026,
            mois=6,
            limit=100,
        )

    assert result.limit == 50
    mock_agg.assert_awaited_once()
    assert mock_agg.await_args.kwargs["limit"] == 50
