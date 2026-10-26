"""Flux SSE : un événement ne doit atteindre que les abonnés de son périmètre."""

from unittest.mock import AsyncMock, MagicMock

from app.services import notification_stream_service as sse


def _reach(event_channels: list[str], user_channels: list[str]) -> bool:
    return bool(set(event_channels) & set(user_channels))


def test_evenement_de_service_atteint_son_perimetre_seulement() -> None:
    event = sse.channels_for_event(service_id=12, region_id=3)

    assert _reach(event, sse.subscribe_channels_for_user(is_national=True))
    assert _reach(event, sse.subscribe_channels_for_user(is_national=False, region_id=3))
    assert _reach(event, sse.subscribe_channels_for_user(is_national=False, service_id=12))

    assert not _reach(event, sse.subscribe_channels_for_user(is_national=False, region_id=4))
    assert not _reach(event, sse.subscribe_channels_for_user(is_national=False, service_id=13))
    assert not _reach(event, sse.subscribe_channels_for_user(is_national=False))


def test_evenement_sans_service_est_global() -> None:
    event = sse.channels_for_event(service_id=None, region_id=None)
    assert _reach(event, sse.subscribe_channels_for_user(is_national=False, region_id=4))


async def test_flux_ferme_quand_le_jeton_n_est_plus_valide() -> None:
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    redis = MagicMock()
    redis.pubsub.return_value = pubsub

    chunks = [
        chunk
        async for chunk in sse.iter_sse_events(
            redis,
            ["c"],
            is_still_authorized=AsyncMock(return_value=False),
            recheck_seconds=0,
        )
    ]

    assert chunks == ["event: session-expired\ndata: {}\n\n"]
    pubsub.unsubscribe.assert_awaited_once_with("c")
