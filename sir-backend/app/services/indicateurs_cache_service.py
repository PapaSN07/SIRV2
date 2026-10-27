"""Cache Redis indicateurs — pattern cache-aside (Sprint 5.2).

Clé : ``indicateurs:{type}:{region_id}:{annee}:{mois}``
TTL : 1 h (3600 s)
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any, TypeVar

from redis.asyncio import Redis

INDICATEURS_CACHE_TTL_SECONDS = 3600

T = TypeVar("T")


def build_cache_key(indicateur_type: str, region_id: int, annee: int, mois: int) -> str:
    return f"indicateurs:{indicateur_type}:{region_id}:{annee}:{mois}"


def build_historique_cache_key(
    indicateur_type: str, region_id: int, annees: int, fin: str | None = None
) -> str:
    base = f"indicateurs:historique:{indicateur_type}:{region_id}:{annees}"
    return f"{base}:{fin}" if fin else base


def build_top_feeders_cache_key(region_id: int, annee: int, mois: int, limit: int) -> str:
    return f"indicateurs:top-feeders:{region_id}:{annee}:{mois}:{limit}"


def period_from_date(value: date | datetime) -> tuple[int, int]:
    return value.year, value.month


async def get_cached(redis: Redis, key: str) -> Any | None:
    raw = await redis.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached(redis: Redis, key: str, payload: Any) -> None:
    await redis.setex(
        key,
        INDICATEURS_CACHE_TTL_SECONDS,
        json.dumps(payload, ensure_ascii=False, default=str),
    )


async def invalidate_period(
    redis: Redis,
    region_id: int,
    annee: int,
    mois: int,
    *,
    indicateurs: tuple[str, ...] = ("end", "saifi", "saidi", "tableau-de-bord"),
) -> None:
    for indicateur in indicateurs:
        await redis.delete(build_cache_key(indicateur, region_id, annee, mois))


async def invalidate_period_from_date(
    redis: Redis,
    region_id: int,
    value: date | datetime,
    *,
    indicateurs: tuple[str, ...] = ("end", "saifi", "saidi", "tableau-de-bord"),
) -> None:
    annee, mois = period_from_date(value)
    await invalidate_period(redis, region_id, annee, mois, indicateurs=indicateurs)


async def get_or_load(
    redis: Redis,
    indicateur_type: str,
    region_id: int,
    annee: int,
    mois: int,
    loader: Callable[[], Awaitable[T]],
) -> T:
    """Cache-aside : lecture cache → miss → loader DB → set cache."""
    key = build_cache_key(indicateur_type, region_id, annee, mois)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached
    result = await loader()
    await set_cached(redis, key, result)
    return result


async def get_or_load_historique(
    redis: Redis,
    indicateur_type: str,
    region_id: int,
    annees: int,
    loader: Callable[[], Awaitable[T]],
    fin: str | None = None,
) -> T:
    """Cache-aside pour séries historiques mensuelles (fin = mois « AAAA-MM » de la série)."""
    key = build_historique_cache_key(indicateur_type, region_id, annees, fin)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached
    result = await loader()
    await set_cached(redis, key, result)
    return result


async def get_or_load_top_feeders(
    redis: Redis,
    region_id: int,
    annee: int,
    mois: int,
    limit: int,
    loader: Callable[[], Awaitable[T]],
) -> T:
    key = build_top_feeders_cache_key(region_id, annee, mois, limit)
    cached = await get_cached(redis, key)
    if cached is not None:
        return cached
    result = await loader()
    await set_cached(redis, key, result)
    return result


def invalidate_indicateurs_cache(
    region_id: int,
    value: date | datetime,
    *,
    indicateurs: tuple[str, ...] = ("end", "saifi", "saidi", "tableau-de-bord"),
) -> None:
    """Invalidation synchrone — appelée depuis workers Celery sans session Redis injectée."""
    import redis

    from app.core.config import settings

    annee, mois = period_from_date(value)
    client = redis.from_url(settings.redis_url, decode_responses=True)
    try:
        for indicateur in indicateurs:
            client.delete(build_cache_key(indicateur, region_id, annee, mois))
    finally:
        client.close()


def invalidate_end_cache(region_id: int, value: date | datetime) -> None:
    invalidate_indicateurs_cache(
        region_id, value, indicateurs=("end", "tableau-de-bord")
    )
