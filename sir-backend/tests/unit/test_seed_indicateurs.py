"""Tests unitaires — seed indicateurs idempotent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.seed.seed_indicateurs import seed_indicateurs

pytestmark = pytest.mark.asyncio


async def test_seed_indicateurs_skips_new_records_when_data_exists() -> None:
    session = AsyncMock()
    existing = MagicMock()
    existing.nombre_clients = 50_000

    async def _execute_side_effect(*_args, **_kwargs):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        return mock_result

    session.execute.side_effect = _execute_side_effect

    await seed_indicateurs(session)

    session.add.assert_not_called()
