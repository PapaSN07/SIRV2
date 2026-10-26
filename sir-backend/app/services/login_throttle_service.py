"""Limitation des tentatives de connexion échouées (anti force brute).

Compteur Redis par login : après ``MAX_FAILED_ATTEMPTS`` échecs dans la
fenêtre ``WINDOW_SECONDS``, le login est bloqué jusqu'à expiration de la clé.
Un succès remet le compteur à zéro.
"""

from fastapi import HTTPException, status
from redis.asyncio import Redis

MAX_FAILED_ATTEMPTS = 5
WINDOW_SECONDS = 15 * 60
_PREFIX = "ratelimit:login:"


def _key(login: str) -> str:
    return f"{_PREFIX}{login.strip().lower()}"


async def ensure_not_locked(redis: Redis, login: str) -> None:
    """Lève 429 si le login a dépassé le nombre d'échecs autorisés."""
    raw = await redis.get(_key(login))
    try:
        failures = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        failures = 0
    if failures >= MAX_FAILED_ATTEMPTS:
        ttl = await redis.ttl(_key(login))
        minutes = max(1, (int(ttl) + 59) // 60) if isinstance(ttl, int) and ttl > 0 else WINDOW_SECONDS // 60
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "status": "error",
                "data": None,
                "error": f"Trop de tentatives échouées. Réessayez dans {minutes} min.",
            },
            headers={"Retry-After": str(minutes * 60)},
        )


async def register_failure(redis: Redis, login: str) -> None:
    key = _key(login)
    failures = await redis.incr(key)
    if failures == 1:
        await redis.expire(key, WINDOW_SECONDS)


async def reset(redis: Redis, login: str) -> None:
    await redis.delete(_key(login))
