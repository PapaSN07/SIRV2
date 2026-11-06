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


def test_periodes_synthese_semaine_samedi_vendredi() -> None:
    from datetime import date, datetime

    from app.services.indicateurs_service import periodes_synthese

    # Vendredi 06/11/2026 : la semaine du 31/10 n'est pas finie → semaine passée 24/10 → 30/10
    semaine, mois, annee = periodes_synthese(date(2026, 11, 6))
    assert semaine[2:] == (datetime(2026, 10, 24), datetime(2026, 10, 31))
    assert mois[2:] == (datetime(2026, 11, 1), datetime(2026, 11, 7))
    assert annee[2:] == (datetime(2026, 1, 1), datetime(2026, 11, 7))
    # Samedi 07/11 : la semaine 31/10 → 06/11 vient de finir
    assert periodes_synthese(date(2026, 11, 7))[0][2:] == (datetime(2026, 10, 31), datetime(2026, 11, 7))


def test_periode_tableau_jour_mois_annee() -> None:
    from datetime import date, datetime

    from app.services.indicateurs_service import resoudre_periode_tableau

    jour = resoudre_periode_tableau("2026-11-06")
    assert (jour.granularite, jour.debut, jour.fin) == ("jour", datetime(2026, 11, 6), datetime(2026, 11, 7))
    mois = resoudre_periode_tableau("2026-02")
    assert (mois.granularite, mois.debut, mois.fin) == ("mois", datetime(2026, 2, 1), datetime(2026, 3, 1))
    annee = resoudre_periode_tableau("2025")
    assert (annee.granularite, annee.debut, annee.fin) == ("annee", datetime(2025, 1, 1), datetime(2026, 1, 1))
    defaut = resoudre_periode_tableau(None, aujourd_hui=date(2026, 12, 15))
    assert (defaut.debut, defaut.fin) == (datetime(2026, 12, 1), datetime(2027, 1, 1))
    assert len({jour.cle_cache, mois.cle_cache, annee.cle_cache}) == 3


def test_requete_clients_transport_sql_server() -> None:
    from datetime import datetime

    from sqlalchemy.dialects import mssql

    from app.repositories.pilotage_repository import requete_clients_transport

    sql = str(requete_clients_transport(datetime(2026, 1, 1), datetime(2026, 2, 1)).compile(dialect=mssql.dialect()))
    assert "BIGINT" in sql.upper() and "IS 1" not in sql
