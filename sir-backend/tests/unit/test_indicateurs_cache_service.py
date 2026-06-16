"""Tests unitaires — indicateurs_cache_service (phase 5.2)."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.indicateurs_cache_service import (
    INDICATEURS_CACHE_TTL_SECONDS,
    build_cache_key,
    get_cached,
    get_or_load,
    invalidate_indicateurs_cache,
    invalidate_period,
    invalidate_period_from_date,
    set_cached,
)


def test_build_cache_key_format() -> None:
    assert build_cache_key("end", 2, 2026, 6) == "indicateurs:end:2:2026:6"
    assert build_cache_key("saifi", 1, 2025, 12) == "indicateurs:saifi:1:2025:12"


@pytest.mark.asyncio
async def test_get_cached_hit(fake_redis) -> None:
    key = build_cache_key("end", 2, 2026, 6)
    await fake_redis.set(key, '{"valeur_mwh": 10.5}')

    result = await get_cached(fake_redis, key)

    assert result == {"valeur_mwh": 10.5}


@pytest.mark.asyncio
async def test_get_cached_miss(fake_redis) -> None:
    key = build_cache_key("saidi", 3, 2026, 1)
    assert await get_cached(fake_redis, key) is None


@pytest.mark.asyncio
async def test_set_cached_applies_ttl(fake_redis) -> None:
    key = build_cache_key("end", 2, 2026, 6)
    payload = {"valeur_mwh": 42.0}

    await set_cached(fake_redis, key, payload)

    assert await fake_redis.get(key) is not None
    ttl = await fake_redis.ttl(key)
    assert 0 < ttl <= INDICATEURS_CACHE_TTL_SECONDS


@pytest.mark.asyncio
async def test_get_or_load_cache_hit_skips_loader(fake_redis) -> None:
    key = build_cache_key("saifi", 2, 2026, 6)
    await fake_redis.set(key, '{"saifi": 0.02}')

    loader = AsyncMock(return_value={"saifi": 0.99})

    result = await get_or_load(fake_redis, "saifi", 2, 2026, 6, loader)

    assert result == {"saifi": 0.02}
    loader.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_load_cache_miss_calls_loader_and_sets(fake_redis) -> None:
    loader = AsyncMock(return_value={"saidi": 1.5})

    result = await get_or_load(fake_redis, "saidi", 2, 2026, 6, loader)

    assert result == {"saidi": 1.5}
    loader.assert_awaited_once()
    key = build_cache_key("saidi", 2, 2026, 6)
    cached = await get_cached(fake_redis, key)
    assert cached == {"saidi": 1.5}


@pytest.mark.asyncio
async def test_invalidate_period_deletes_indicateur_keys(fake_redis) -> None:
    await fake_redis.set(build_cache_key("end", 2, 2026, 6), "1")
    await fake_redis.set(build_cache_key("saifi", 2, 2026, 6), "2")
    await fake_redis.set(build_cache_key("saidi", 2, 2026, 6), "3")
    await fake_redis.set(build_cache_key("end", 2, 2026, 7), "4")

    await invalidate_period(fake_redis, 2, 2026, 6, indicateurs=("end", "saifi", "saidi"))

    assert await fake_redis.get(build_cache_key("end", 2, 2026, 6)) is None
    assert await fake_redis.get(build_cache_key("saifi", 2, 2026, 6)) is None
    assert await fake_redis.get(build_cache_key("saidi", 2, 2026, 6)) is None
    assert await fake_redis.get(build_cache_key("end", 2, 2026, 7)) == "4"


@pytest.mark.asyncio
async def test_invalidate_period_from_date(fake_redis) -> None:
    await fake_redis.set(build_cache_key("end", 5, 2026, 3), "x")

    await invalidate_period_from_date(
        fake_redis,
        5,
        datetime(2026, 3, 15, 10, 0, 0),
        indicateurs=("end",),
    )

    assert await fake_redis.get(build_cache_key("end", 5, 2026, 3)) is None


def test_invalidate_indicateurs_cache_sync() -> None:
    mock_client = MagicMock()
    with patch("redis.from_url", return_value=mock_client):
        invalidate_indicateurs_cache(
            2,
            datetime(2026, 6, 12),
            indicateurs=("end", "saifi"),
        )

    mock_client.delete.assert_any_call("indicateurs:end:2:2026:6")
    mock_client.delete.assert_any_call("indicateurs:saifi:2:2026:6")
    assert mock_client.delete.call_count == 2
    mock_client.close.assert_called_once()
