"""Service — publication événements temps réel (Sprint 8.4)."""

import json
import logging
from datetime import datetime

from redis.asyncio import Redis

from app.core.config import settings
from app.schemas.notifications import NotificationEvent

logger = logging.getLogger(__name__)

CHANNEL_SERVICE_PREFIX = "sir:notifications:service:"
CHANNEL_BROADCAST = "sir:notifications:broadcast"


def _service_channel(service_id: int | None) -> str:
    if service_id is None:
        return CHANNEL_BROADCAST
    return f"{CHANNEL_SERVICE_PREFIX}{service_id}"


async def publish_event(
    *,
    event_type: str,
    entity_type: str,
    entity_id: int,
    message: str,
    service_id: int | None,
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
        await redis.publish(_service_channel(service_id), payload)
        await redis.publish(CHANNEL_BROADCAST, payload)
    finally:
        await redis.aclose()


async def subscribe_channels_for_user(user_service_id: int | None, is_national: bool) -> list[str]:
    channels = [CHANNEL_BROADCAST]
    if is_national:
        return channels
    if user_service_id is not None:
        channels.append(_service_channel(user_service_id))
    return channels


async def iter_sse_events(
    redis: Redis,
    channels: list[str],
    *,
    heartbeat_seconds: int = 30,
):
    """Générateur async SSE : heartbeat + messages Redis."""
    import asyncio
    import time

    pubsub = redis.pubsub()
    await pubsub.subscribe(*channels)
    try:
        last_heartbeat = time.monotonic()
        while True:
            now = time.monotonic()
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
        await pubsub.close()
