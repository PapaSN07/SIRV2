"""Tests unitaires — seed interruptions idempotent."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.seed.seed_interruptions import seed_interruptions

pytestmark = pytest.mark.asyncio


async def test_seed_interruptions_skips_when_marker_exists() -> None:
    session = AsyncMock()
    existing_interruption = MagicMock()

    call_count = 0

    async def _execute_side_effect(*_args, **_kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        # First lookups return entities; interruption marker lookup returns existing
        if call_count >= 10:
            mock_result.scalar_one_or_none.return_value = existing_interruption
        else:
            mock_result.scalar_one_or_none.return_value = MagicMock(id=1, code="X")
        return mock_result

    session.execute.side_effect = _execute_side_effect

    await seed_interruptions(session)

    session.add.assert_not_called()
