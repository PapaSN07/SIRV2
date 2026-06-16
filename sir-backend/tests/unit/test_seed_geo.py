"""Tests unitaires — seed géographique idempotent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.seed.seed_geo import seed_geo

pytestmark = pytest.mark.asyncio


async def test_seed_geo_idempotent_no_duplicate_insert() -> None:
    """seed_geo ne doit pas appeler db.add si les codes existent déjà."""
    session = AsyncMock()

    # Simule : tous les select retournent un enregistrement existant
    existing = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    session.execute.return_value = mock_result

    await seed_geo(session)

    session.add.assert_not_called()
    session.flush.assert_awaited()
