"""Tests unitaires — seed réseau idempotent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.seed.seed_reseau import seed_reseau

pytestmark = pytest.mark.asyncio


async def test_seed_reseau_idempotent_no_duplicate_insert() -> None:
    session = AsyncMock()
    existing = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    session.execute.return_value = mock_result

    await seed_reseau(session)

    session.add.assert_not_called()
    session.flush.assert_awaited()
