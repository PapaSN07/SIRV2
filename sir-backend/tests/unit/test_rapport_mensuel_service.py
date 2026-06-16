"""Tests unitaires — collecte rapport mensuel distribution (phases 6.2 + 6.5)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.common import PaginatedResponse
from app.schemas.indicateurs import (
    EndAggregateResponse,
    EndIndicateurResponse,
    EndServiceItemResponse,
    SaifiIndicateurResponse,
    SaifiSaidiAggregateResponse,
    SaidiIndicateurResponse,
    TopFeederItemResponse,
    TopFeedersResponse,
)
from app.services import rapport_mensuel_service as svc

pytestmark = pytest.mark.asyncio


def _end_response() -> EndIndicateurResponse:
    return EndIndicateurResponse(
        aggregate=EndAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=6,
            end_mwh=25.0,
            nombre_interruptions=5,
        ),
        services=PaginatedResponse(
            items=[
                EndServiceItemResponse(service_id=1, end_mwh=10.0, nombre_interruptions=2),
                EndServiceItemResponse(service_id=2, end_mwh=15.0, nombre_interruptions=3),
            ],
            total=2,
            page=1,
            page_size=500,
        ),
    )


def _saifi_response() -> SaifiIndicateurResponse:
    return SaifiIndicateurResponse(
        aggregate=SaifiSaidiAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=6,
            saifi=1.2,
            saidi=0.0,
            nombre_interruptions=5,
            total_clients_reference=10000,
        ),
        services=None,
    )


def _saidi_response() -> SaidiIndicateurResponse:
    return SaidiIndicateurResponse(
        aggregate=SaifiSaidiAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=6,
            saifi=0.0,
            saidi=45.5,
            nombre_interruptions=5,
            total_clients_reference=10000,
        ),
        services=None,
    )


def _top_feeders_response(limit: int = 10) -> TopFeedersResponse:
    return TopFeedersResponse(
        niveau="national",
        scope_id=None,
        annee=2026,
        mois=6,
        limit=limit,
        items=[
            TopFeederItemResponse(
                feeder_id=1,
                code="F01",
                libelle="Feeder Alpha",
                service_id=1,
                end_mwh=8.5,
                nombre_interruptions=2,
            ),
            TopFeederItemResponse(
                feeder_id=2,
                code="F02",
                libelle="Feeder Beta",
                service_id=2,
                end_mwh=5.0,
                nombre_interruptions=1,
            ),
        ],
    )


async def test_collect_mensuel_distribution_uses_indicateurs_service() -> None:
    db = AsyncMock()
    redis = AsyncMock()
    user = AsyncMock()

    with patch(
        "app.services.indicateurs_service.get_end",
        new_callable=AsyncMock,
        return_value=_end_response(),
    ) as end_mock, patch(
        "app.services.indicateurs_service.get_saifi",
        new_callable=AsyncMock,
        return_value=_saifi_response(),
    ) as saifi_mock, patch(
        "app.services.indicateurs_service.get_saidi",
        new_callable=AsyncMock,
        return_value=_saidi_response(),
    ) as saidi_mock, patch(
        "app.services.indicateurs_service.get_top_feeders",
        new_callable=AsyncMock,
        return_value=_top_feeders_response(),
    ) as top_mock:
        result = await svc.collect_mensuel_distribution_data(
            db,
            redis,
            user,
            annee=2026,
            mois=6,
            region_id=None,
        )

    end_mock.assert_awaited_once()
    saifi_mock.assert_awaited_once()
    saidi_mock.assert_awaited_once()
    top_mock.assert_awaited_once()
    assert result.end.aggregate.end_mwh == 25.0
    assert result.saifi.aggregate.saifi == 1.2
    assert result.saidi.aggregate.saidi == 45.5
    assert result.end.services is not None
    assert len(result.end.services.items) == 2


async def test_collect_mensuel_includes_top_feeders_section() -> None:
    db = AsyncMock()
    redis = AsyncMock()
    user = AsyncMock()

    with patch(
        "app.services.indicateurs_service.get_end",
        new_callable=AsyncMock,
        return_value=_end_response(),
    ), patch(
        "app.services.indicateurs_service.get_saifi",
        new_callable=AsyncMock,
        return_value=_saifi_response(),
    ), patch(
        "app.services.indicateurs_service.get_saidi",
        new_callable=AsyncMock,
        return_value=_saidi_response(),
    ), patch(
        "app.services.indicateurs_service.get_top_feeders",
        new_callable=AsyncMock,
        return_value=_top_feeders_response(limit=5),
    ) as top_mock:
        result = await svc.collect_mensuel_distribution_data(
            db,
            redis,
            user,
            annee=2026,
            mois=6,
            region_id=None,
            top_feeders_limit=5,
        )

    top_mock.assert_awaited_once_with(
        db,
        redis,
        user,
        annee=2026,
        mois=6,
        region_id=None,
        limit=5,
    )
    assert result.top_feeders_limit == 5
    assert len(result.top_feeders.items) == 2
    assert result.top_feeders.items[0].code == "F01"
    assert result.top_feeders.items[0].end_mwh == 8.5
