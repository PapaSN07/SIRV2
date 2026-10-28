"""SAIFI/SAIDI d'un périmètre : numérateur et base clients sommés sur tous ses services."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.pilotage_repository import ClientsDureeRow
from app.services import saifi_saidi_service

PREFIXE = "app.services.saifi_saidi_service.pilotage_repository"


@pytest.mark.asyncio
async def test_base_clients_du_perimetre_entier() -> None:
    # Interruptions sur le service 2, base clients portée par le service 1 (représentant régional)
    with (
        patch(f"{PREFIXE}.sommer_clients", AsyncMock(return_value=ClientsDureeRow(500, 550.0, 2))),
        patch(f"{PREFIXE}.mois_derniere_apparition", AsyncMock(return_value=(2026, 4))),
        patch(f"{PREFIXE}.clients_reference_exacte", AsyncMock(return_value=10_000)) as ref,
    ):
        r = await saifi_saidi_service.calculer_perimetre(
            None, [1, 2], datetime(2026, 4, 1), datetime(2026, 5, 1)  # type: ignore[arg-type]
        )
    ref.assert_awaited_once_with(None, [1, 2], 2026, 4)
    assert (r.saifi, r.saidi, r.nombre_interruptions, r.total_clients_reference) == (0.05, 0.055, 2, 10_000)


@pytest.mark.asyncio
async def test_mois_sans_interruption_base_du_mois() -> None:
    with (
        patch(f"{PREFIXE}.sommer_clients", AsyncMock(return_value=ClientsDureeRow(0, 0.0, 0))),
        patch(f"{PREFIXE}.mois_derniere_apparition", AsyncMock(return_value=None)),
        patch(f"{PREFIXE}.clients_reference_exacte", AsyncMock(return_value=8_000)) as ref,
    ):
        r = await saifi_saidi_service.calculer_perimetre(
            None, [1], datetime(2025, 3, 1), datetime(2025, 4, 1)  # type: ignore[arg-type]
        )
    ref.assert_awaited_once_with(None, [1], 2025, 3)
    assert r.saifi == 0.0 and r.total_clients_reference == 8_000


def test_sommes_clients_en_bigint_et_float() -> None:
    """Σ clients sur une année nationale dépasse un INT SQL Server (erreur 8115)."""
    from sqlalchemy import select
    from sqlalchemy.dialects import mssql

    from app.models.interruptions import Interruption
    from app.repositories import pilotage_repository as repo

    sql = str(select(*repo._sommes_clients()).select_from(Interruption).compile(dialect=mssql.dialect()))
    assert "AS BIGINT" in sql and "AS FLOAT" in sql
