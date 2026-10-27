"""Rapports planifiés : périodes, regroupement par région, pièce jointe."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import rapport_planifie_service as svc
from app.services.rapport_generation_service import semaine_precedente

pytestmark = pytest.mark.asyncio


async def test_semaine_precedente_lundi_au_dimanche() -> None:
    # Lundi 2 novembre 2026 → semaine du 26 octobre au 1er novembre
    assert semaine_precedente(date(2026, 11, 2)) == (date(2026, 10, 26), date(2026, 11, 1))
    # Un mercredi donne aussi la semaine complète précédente
    assert semaine_precedente(date(2026, 11, 4)) == (date(2026, 10, 26), date(2026, 11, 1))


async def test_periode_mensuelle_mois_precedent() -> None:
    assert svc.periode(svc.MENSUEL, date(2026, 11, 1)) == (date(2026, 10, 1), date(2026, 10, 31))
    assert svc.periode(svc.MENSUEL, date(2027, 1, 1)) == (date(2026, 12, 1), date(2026, 12, 31))


def _dest(i: int, service_id: int | None) -> SimpleNamespace:
    return SimpleNamespace(id=i, service_id=service_id, email=f"d{i}@senelec.sn")


async def test_un_rapport_par_region_et_un_email_par_destinataire() -> None:
    db = AsyncMock()
    destinataires = [_dest(1, 10), _dest(2, 11), _dest(3, 20), _dest(4, None)]
    regions = {10: 1, 11: 1, 20: 2}
    rapports = iter(range(100, 200))
    emails = iter(range(500, 600))

    async def creer_rapport(db, **kw):
        return SimpleNamespace(id=next(rapports), **kw)

    async def creer_email(db, **kw):
        return SimpleNamespace(id=next(emails), **kw)

    with patch.object(svc.dest_repo, "list_actifs_avec_email", AsyncMock(return_value=destinataires)), patch.object(
        svc.rapport_repository, "get_compte_systeme", AsyncMock(return_value=SimpleNamespace(id=9))
    ), patch.object(
        svc.end_repository, "get_region_id_for_service", AsyncMock(side_effect=lambda db, s: regions[s])
    ), patch.object(svc.rapport_repository, "create_rapport", side_effect=creer_rapport) as cr, patch.object(
        svc.rapport_generation_service, "execute_generation", AsyncMock()
    ) as gen, patch.object(svc.email_repository, "create_pending", side_effect=creer_email) as ce:
        bilan = await svc.envoyer(db, svc.HEBDOMADAIRE, date(2026, 11, 2))

    assert bilan.rapports == 3  # région 1, région 2, national
    assert len(bilan.emails) == 4
    regions_generees = sorted((c.kwargs["region_id"] or 0) for c in cr.call_args_list)
    assert regions_generees == [0, 1, 2]
    assert all(c.kwargs["notifier"] is False for c in gen.call_args_list)
    assert all(c.kwargs["entity_type"] == "rapport" for c in ce.call_args_list)


async def test_sans_compte_systeme_aucun_envoi() -> None:
    with patch.object(svc.dest_repo, "list_actifs_avec_email", AsyncMock(return_value=[_dest(1, None)])), patch.object(
        svc.rapport_repository, "get_compte_systeme", AsyncMock(return_value=None)
    ):
        bilan = await svc.envoyer(AsyncMock(), svc.MENSUEL, date(2026, 11, 1))
    assert bilan.rapports == 0 and bilan.erreurs


async def test_piece_jointe_du_rapport(tmp_path) -> None:
    from app.services import email_service

    fichier = tmp_path / "hebdomadaire_x.pdf"
    fichier.write_bytes(b"%PDF-1.4")
    record = SimpleNamespace(entity_type="rapport", entity_id=100)
    with patch(
        "app.repositories.rapport_repository.get_by_id",
        AsyncMock(return_value=SimpleNamespace(file_path=str(fichier))),
    ):
        assert await email_service._piece_jointe(AsyncMock(), record) == fichier
    assert await email_service._piece_jointe(AsyncMock(), SimpleNamespace(entity_type="interruption", entity_id=1)) is None


async def test_export_hebdomadaire_pdf_et_excel(tmp_path) -> None:
    from datetime import datetime

    from app.repositories.rapport_journalier_repository import JournalierInterruptionRow
    from app.services.rapport_export_service import export_journalier
    from app.services.rapport_journalier_service import JournalierReportData

    ligne = JournalierInterruptionRow(
        id=1, numero_interruption=26104, type_direction="distribution", statut="valide",
        date_apparition=datetime(2026, 10, 27, 6, 30), date_remise=datetime(2026, 10, 27, 8, 0),
        feeder_code="HANN", feeder_libelle="HANN 30kV", end_mwh=1.2, nombre_clients=1200,
        service_id=1, libelle_reseau="HANN 30kV",
    )
    data = JournalierReportData(
        report_date=date(2026, 10, 26), region_id=1, service_id=None, include_transport=False,
        end_cumulee_mwh=1.2, nombre_interruptions=1, interruptions=[ligne], feeders=[],
        date_fin=date(2026, 11, 1),
    )
    assert data.titre_periode == "Rapport hebdomadaire SIR — du 26/10/2026 au 01/11/2026"
    for fmt in ("pdf", "xlsx"):
        path = tmp_path / f"hebdo.{fmt}"
        export_journalier(path, format=fmt, data=data)
        assert path.stat().st_size > 500
