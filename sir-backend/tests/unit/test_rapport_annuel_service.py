"""Tests unitaires — collecte rapport annuel (phase 6.4)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.indicateurs import (
    EndAggregateResponse,
    EndIndicateurResponse,
    HistoriquePointResponse,
    HistoriqueResponse,
    SaifiIndicateurResponse,
    SaifiSaidiAggregateResponse,
    SaidiIndicateurResponse,
    TopFeedersResponse,
)
from app.services import rapport_annuel_service as svc

pytestmark = pytest.mark.asyncio


def _monthly_end(mois: int, value: float) -> EndIndicateurResponse:
    return EndIndicateurResponse(
        aggregate=EndAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=mois,
            end_mwh=value,
            nombre_interruptions=1,
        ),
        services=None,
    )


def _monthly_saifi(mois: int) -> SaifiIndicateurResponse:
    return SaifiIndicateurResponse(
        aggregate=SaifiSaidiAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=mois,
            saifi=1.0,
            saidi=0.0,
            nombre_interruptions=1,
            total_clients_reference=1000,
        ),
        services=None,
    )


def _monthly_saidi(mois: int) -> SaidiIndicateurResponse:
    return SaidiIndicateurResponse(
        aggregate=SaifiSaidiAggregateResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=mois,
            saifi=0.0,
            saidi=10.0,
            nombre_interruptions=1,
            total_clients_reference=1000,
        ),
        services=None,
    )


def _historique(indicateur_type: str) -> HistoriqueResponse:
    return HistoriqueResponse(
        type=indicateur_type,
        niveau="national",
        scope_id=None,
        annees=1,
        points=[HistoriquePointResponse(annee=2026, mois=6, valeur=5.0)],
    )


async def test_collect_annuel_distribution_includes_historique_and_top_feeders() -> None:
    db = AsyncMock()
    redis = AsyncMock()
    user = AsyncMock()

    async def _get_end(*args, **kwargs):
        return _monthly_end(kwargs["mois"], float(kwargs["mois"]))

    with patch(
        "app.services.indicateurs_service.get_end",
        side_effect=_get_end,
    ), patch(
        "app.services.indicateurs_service.get_saifi",
        side_effect=lambda *a, **k: _monthly_saifi(k["mois"]),
    ), patch(
        "app.services.indicateurs_service.get_saidi",
        side_effect=lambda *a, **k: _monthly_saidi(k["mois"]),
    ), patch(
        "app.services.indicateurs_service.get_historique",
        side_effect=lambda *a, **k: _historique(k["indicateur_type"]),
    ), patch(
        "app.services.indicateurs_service.get_top_feeders",
        new_callable=AsyncMock,
        return_value=TopFeedersResponse(
            niveau="national",
            scope_id=None,
            annee=2026,
            mois=6,
            limit=10,
            items=[],
        ),
    ):
        result = await svc.collect_annuel_data(
            db,
            redis,
            user,
            annee=2026,
            direction="distribution",
            region_id=None,
            top_limit=10,
        )

    assert len(result.serie_civile) == 12
    assert result.total_end_annee == sum(range(1, 13))
    assert result.historique_end is not None
    assert result.historique_saifi is not None
    assert result.historique_saidi is not None
    assert result.objectifs_note.startswith("Objectifs CRSE")
