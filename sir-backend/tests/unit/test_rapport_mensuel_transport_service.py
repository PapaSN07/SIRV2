"""Tests unitaires — collecte rapport mensuel transport (phase 6.3)."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.rapport_transport_repository import (
    TransportEquipementRow,
    TransportInterruptionRow,
)
from app.services import rapport_mensuel_transport_service as svc

pytestmark = pytest.mark.asyncio


async def test_collect_mensuel_transport_aggregates_end() -> None:
    interruptions = [
        TransportInterruptionRow(
            id=1,
            numero_interruption=10,
            type_direction="transport",
            statut="cloture",
            date_apparition=datetime(2026, 6, 5, 8, 0),
            date_remise=datetime(2026, 6, 5, 10, 0),
            equipement_code="EQ01",
            equipement_libelle="Ligne 225",
            source_libelle="PS Dakar",
            end_mwh=12.0,
            puissance_transit_mw=150.0,
            duree_minutes=120,
        )
    ]
    equipements = [
        TransportEquipementRow(
            equipement_id=1,
            code="EQ01",
            libelle="Ligne 225",
            nombre_interruptions=1,
            end_mwh=12.0,
        )
    ]
    db = AsyncMock()

    with patch(
        "app.repositories.rapport_transport_repository.list_interruptions_for_month",
        new_callable=AsyncMock,
        return_value=interruptions,
    ), patch(
        "app.repositories.rapport_transport_repository.aggregate_equipements_for_month",
        new_callable=AsyncMock,
        return_value=equipements,
    ):
        result = await svc.collect_mensuel_transport_data(
            db,
            annee=2026,
            mois=6,
            top_equipements_limit=5,
        )

    assert result.nombre_interruptions == 1
    assert result.end_cumulee_mwh == 12.0
    assert result.top_equipements_limit == 5
    assert len(result.top_equipements) == 1
