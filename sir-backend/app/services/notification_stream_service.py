"""Service — publication événements temps réel (Sprint 8.4).

Canaux Redis (un événement n'est publié que sur les canaux de son périmètre) :
- ``sir:notifications:national``          rôles nationaux (admins, dispatcher, superadmin)
- ``sir:notifications:region:{id}``       BCC / BRC de la région
- ``sir:notifications:service:{id}``      Superviseur du service
- ``sir:notifications:broadcast``         événements sans service (globaux) uniquement
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from redis.asyncio import Redis

from app.core.config import settings
from app.schemas.notifications import NotificationEvent

logger = logging.getLogger(__name__)

CHANNEL_SERVICE_PREFIX = "sir:notifications:service:"
CHANNEL_REGION_PREFIX = "sir:notifications:region:"
CHANNEL_NATIONAL = "sir:notifications:national"
CHANNEL_BROADCAST = "sir:notifications:broadcast"

# Fréquence de revérification du jeton pendant un flux ouvert (secondes)
TOKEN_RECHECK_SECONDS = 60


def _service_channel(service_id: int) -> str:
    return f"{CHANNEL_SERVICE_PREFIX}{service_id}"


def _region_channel(region_id: int) -> str:
    return f"{CHANNEL_REGION_PREFIX}{region_id}"


def channels_for_event(service_id: int | None, region_id: int | None) -> list[str]:
    """Canaux sur lesquels publier un événement, selon son périmètre."""
    if service_id is None:
        return [CHANNEL_BROADCAST]
    channels = [_service_channel(service_id), CHANNEL_NATIONAL]
    if region_id is not None:
        channels.append(_region_channel(region_id))
    return channels


async def publish_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    message: str,
    service_id: int | None,
    region_id: int | None = None,
) -> None:
    event = NotificationEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
        service_id=service_id,
        created_at=datetime.now(),
    )
    payload = event.model_dump_json()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        for channel in channels_for_event(service_id, region_id):
            await redis.publish(channel, payload)
    finally:
        await redis.aclose()


def subscribe_channels_for_user(
    *,
    is_national: bool,
    region_id: int | None = None,
    service_id: int | None = None,
) -> list[str]:
    """Canaux d'abonnement d'un utilisateur : jamais ceux d'un autre périmètre."""
    channels = [CHANNEL_BROADCAST]
    if is_national:
        channels.append(CHANNEL_NATIONAL)
    elif region_id is not None:
        channels.append(_region_channel(region_id))
    elif service_id is not None:
        channels.append(_service_channel(service_id))
    return channels


async def iter_sse_events(
    redis: Redis,
    channels: list[str],
    *,
    heartbeat_seconds: int = 30,
    is_still_authorized: Callable[[], Awaitable[bool]] | None = None,
    recheck_seconds: int = TOKEN_RECHECK_SECONDS,
) -> AsyncIterator[str]:
    """Générateur async SSE : heartbeat + messages Redis.

    Si ``is_still_authorized`` est fourni, il est rappelé toutes les
    ``recheck_seconds`` : le flux se ferme dès que le jeton est expiré ou révoqué.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)
    try:
        last_heartbeat = last_check = time.monotonic()
        while True:
            now = time.monotonic()
            if is_still_authorized is not None and now - last_check >= recheck_seconds:
                last_check = now
                if not await is_still_authorized():
                    yield "event: session-expired\ndata: {}\n\n"
                    return
            if now - last_heartbeat >= heartbeat_seconds:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                data = message.get("data")
                if isinstance(data, str):
                    yield f"data: {data}\n\n"
                else:
                    yield f"data: {json.dumps(data)}\n\n"
            else:
                await asyncio.sleep(0.2)
    finally:
        await pubsub.unsubscribe(*channels)
        await pubsub.aclose()
