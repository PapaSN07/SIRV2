"""Rapport mensuel : carte du poids de l'END par service (positions SIG, parts, PDF, Excel)."""

from types import SimpleNamespace as N

from openpyxl import load_workbook

from app.services.rapport_export_pdf_service import cadre_dakar_contient, dessiner_carte_end
from app.services.rapport_mensuel_service import assembler_carte_end


def _carte():
    points = [(1, -17.44, 14.69), (1, -17.46, 14.70), (1, -17.40, 14.68), (2, -16.27, 12.58), (2, -16.30, 12.60)]
    items = [
        N(service_id=1, end_mwh=300.0, nombre_interruptions=30),
        N(service_id=2, end_mwh=100.0, nombre_interruptions=10),
        N(service_id=3, end_mwh=0.0, nombre_interruptions=0),
    ]
    return assembler_carte_end(
        [i for i in items if i.end_mwh > 0], 400.0, {1: ("SDDV", "Dakar ville"), 2: ("DRS", "Sud")}, points
    )


def test_parts_et_positions() -> None:
    carte = _carte()
    sddv, drs = carte.services
    assert (sddv.code, sddv.part_pct, drs.part_pct) == ("SDDV", 75.0, 25.0)
    assert (sddv.longitude, sddv.latitude) == (-17.44, 14.69)  # médiane des nœuds du service
    assert cadre_dakar_contient(sddv.longitude, sddv.latitude) and not cadre_dakar_contient(drs.longitude, drs.latitude)
    assert len(carte.fond) == 5


def test_service_sans_noeud_sig() -> None:
    carte = assembler_carte_end([N(service_id=9, end_mwh=5.0, nombre_interruptions=1)], 5.0, {}, [])
    assert carte.services[0].longitude is None and carte.services[0].part_pct == 100.0


def test_page_pdf(tmp_path) -> None:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    chemin = tmp_path / "carte.pdf"
    pdf = canvas.Canvas(str(chemin), pagesize=landscape(A4))
    dessiner_carte_end(pdf, _carte(), titre="Poids de l'END par service — 10/2026")
    pdf.showPage()
    pdf.save()
    assert chemin.read_bytes().startswith(b"%PDF") and chemin.stat().st_size > 1000


def test_feuille_excel(tmp_path) -> None:
    from app.services.rapport_export_excel_service import export_mensuel_distribution_xlsx

    vide = N(items=[])
    data = N(
        annee=2026,
        mois=10,
        region_id=None,
        top_feeders_limit=10,
        end=N(aggregate=N(end_mwh=400.0, nombre_interruptions=40, niveau="national"), services=vide),
        saifi=N(aggregate=N(saifi=1.0), services=vide),
        saidi=N(aggregate=N(saidi=0.5), services=vide),
        top_feeders=N(items=[]),
        carte_end=_carte(),
    )
    chemin = tmp_path / "m.xlsx"
    export_mensuel_distribution_xlsx(chemin, data)  # type: ignore[arg-type]
    feuille = load_workbook(chemin)["Poids END par service"]
    assert [c.value for c in feuille[2]][:4] == ["SDDV", "Dakar ville", 300.0, 75.0]
