"""Synthèse SAIFI/SAIDI de l'accueil : HTA / HTB par la cause (décision SENELEC du 25/11/2026).

HTB = interruptions distribution dont la cause est HTB / production / black start ; HTA = les
autres. Les interruptions transport / OMVG ne comptent plus dans la synthèse. HTB et total sont
renseignés à tous les niveaux (national, région, service), et HTA + HTB = total.
Tests écrits avant le code (circuit « tests avant le code »).
"""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.repositories.pilotage_repository import ClientsDureeRow
from app.services import indicateurs_service as svc
from app.services.saifi_saidi_service import SaifiSaidiPerimetre

REFERENCE = 2_600_000
AUJOURD_HUI = date(2026, 11, 25)

# Même base clients pour les trois calculs (dénominateur commun) : HTA + HTB = total
_PAR_RESEAU: dict[str | None, SaifiSaidiPerimetre] = {
    "hta": SaifiSaidiPerimetre(saifi=0.3, saidi=0.6, nombre_interruptions=30, total_clients_reference=REFERENCE),
    "htb": SaifiSaidiPerimetre(saifi=0.1, saidi=0.25, nombre_interruptions=4, total_clients_reference=REFERENCE),
    None: SaifiSaidiPerimetre(saifi=0.4, saidi=0.85, nombre_interruptions=34, total_clients_reference=REFERENCE),
}


async def _calculer_perimetre(
    db: object,
    service_ids: list[int],
    debut: datetime,
    fin: datetime,
    today: date | None = None,
    reseau: str | None = None,
) -> SaifiSaidiPerimetre:
    return _PAR_RESEAU[reseau]


def _scope(niveau: str, scope_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(niveau=niveau, scope_id=scope_id, service_ids=[1, 2], cache_region_id=scope_id or 0)


async def _synthese(niveau: str, scope_id: int | None) -> tuple:
    """Appelle get_synthese_saifi_saidi avec base, cache et périmètre simulés."""
    calcul = AsyncMock(side_effect=_calculer_perimetre)
    transport = AsyncMock(return_value=ClientsDureeRow(clients=999_999, client_heures=999_999.0, nombre=77))
    with (
        patch.object(svc, "_resolve_scope", return_value=_scope(niveau, scope_id)),
        patch.object(svc, "_load_service_ids", AsyncMock(return_value=[1, 2])),
        patch.object(svc, "check_service_scope", return_value=None),
        patch.object(svc, "get_cached", AsyncMock(return_value=None)),
        patch.object(svc, "set_cached", AsyncMock(return_value=None)),
        patch.object(svc.saifi_saidi_service, "calculer_perimetre", calcul),
        patch.object(svc.pilotage_repository, "sommer_clients_transport", transport),
    ):
        reponse = await svc.get_synthese_saifi_saidi(
            AsyncMock(), AsyncMock(), SimpleNamespace(id=1, user_roles=[]),  # type: ignore[arg-type]
            aujourd_hui=AUJOURD_HUI,
        )
    return reponse, calcul, transport


NIVEAUX = [("national", None), ("region", 1), ("service", 5)]


@pytest.mark.asyncio
@pytest.mark.parametrize(("niveau", "scope_id"), NIVEAUX)
async def test_htb_et_total_renseignes_a_tous_les_niveaux(niveau: str, scope_id: int | None) -> None:
    """HTB et total ne sont plus réservés à la vue nationale."""
    reponse, _, _ = await _synthese(niveau, scope_id)
    assert [p.cle for p in reponse.periodes] == ["semaine", "mois", "annee"]
    for periode in reponse.periodes:
        assert periode.htb is not None, periode.cle
        assert periode.total is not None, periode.cle


@pytest.mark.asyncio
@pytest.mark.parametrize(("niveau", "scope_id"), NIVEAUX)
async def test_hta_htb_calcules_par_la_cause(niveau: str, scope_id: int | None) -> None:
    """HTA = calcul reseau='hta', HTB = calcul reseau='htb', pour chaque période."""
    reponse, calcul, _ = await _synthese(niveau, scope_id)
    reseaux = [
        appel.kwargs.get("reseau", appel.args[5] if len(appel.args) > 5 else None) for appel in calcul.await_args_list
    ]
    assert reseaux.count("hta") == 3
    assert reseaux.count("htb") == 3
    for periode in reponse.periodes:
        assert (periode.hta.saifi, periode.hta.saidi, periode.hta.nombre_interruptions) == (0.3, 0.6, 30)
        assert (periode.htb.saifi, periode.htb.saidi, periode.htb.nombre_interruptions) == (0.1, 0.25, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize(("niveau", "scope_id"), NIVEAUX)
async def test_total_egal_hta_plus_htb(niveau: str, scope_id: int | None) -> None:
    """Total = HTA + HTB (SAIFI, SAIDI et nombre d'interruptions)."""
    reponse, _, _ = await _synthese(niveau, scope_id)
    for periode in reponse.periodes:
        hta, htb, total = periode.hta, periode.htb, periode.total
        assert total.nombre_interruptions == hta.nombre_interruptions + htb.nombre_interruptions == 34
        assert abs(total.saifi - (hta.saifi + htb.saifi)) < 1e-6
        assert abs(total.saidi - (hta.saidi + htb.saidi)) < 1e-6


@pytest.mark.asyncio
@pytest.mark.parametrize(("niveau", "scope_id"), NIVEAUX)
async def test_transport_omvg_hors_synthese(niveau: str, scope_id: int | None) -> None:
    """Les interruptions transport / OMVG ne sont plus lues pour la synthèse."""
    reponse, _, transport = await _synthese(niveau, scope_id)
    transport.assert_not_awaited()
    for periode in reponse.periodes:
        assert periode.total.nombre_interruptions != 30 + 77


@pytest.mark.asyncio
@pytest.mark.parametrize(("niveau", "scope_id"), NIVEAUX)
async def test_base_clients_du_perimetre_inchangee(niveau: str, scope_id: int | None) -> None:
    """total_clients_reference reste la base clients du périmètre."""
    reponse, calcul, _ = await _synthese(niveau, scope_id)
    assert reponse.total_clients_reference == REFERENCE
    assert reponse.niveau == niveau and reponse.scope_id == scope_id
    for appel in calcul.await_args_list:
        service_ids = appel.kwargs.get("service_ids", appel.args[1] if len(appel.args) > 1 else None)
        assert service_ids == [1, 2]
