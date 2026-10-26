"""Export PDF partagé — rapports CRSE (Sprint 6).

# TODO(CRSE): remplacer par les gabarits officiels SAQS.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from app.services.rapport_annuel_service import AnnuelReportData
from app.services.rapport_journalier_service import JournalierReportData
from app.services.rapport_mensuel_service import MensuelDistributionReportData
from app.services.rapport_mensuel_transport_service import MensuelTransportReportData


def _journalier_scope_label(data: JournalierReportData) -> str:
    if data.service_id is not None:
        return f"Service {data.service_id}"
    if data.region_id is not None:
        return f"Région {data.region_id}"
    return "National"


def _mensuel_scope_label(data: MensuelDistributionReportData) -> str:
    if data.region_id is not None:
        return f"Région {data.region_id}"
    return data.end.aggregate.niveau.capitalize()


def export_journalier_pdf(path: Path, data: JournalierReportData) -> None:
    pdf = canvas.Canvas(str(path), pagesize=landscape(A4))
    width, height = landscape(A4)
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, f"Rapport journalier SIR — {data.report_date.isoformat()}")
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Périmètre : {_journalier_scope_label(data)}")
    y -= 14
    pdf.drawString(
        40,
        y,
        f"Interruptions : {data.nombre_interruptions} · END cumulée : {data.end_cumulee_mwh:.4f} MWh",
    )
    y -= 14
    if data.include_transport:
        pdf.drawString(40, y, "Inclut transport HTB (ADMIN_SAQS national)")
        y -= 14
    pdf.drawString(40, y, "Template placeholder CRSE — validation SAQS requise.")
    y -= 24

    pdf.setFont("Helvetica-Bold", 9)
    headers = ["N°", "Type", "Statut", "Apparition", "Feeder/Réseau", "END (MWh)", "Clients"]
    col_x = [40, 80, 130, 190, 290, 480, 560]
    for idx, header in enumerate(headers):
        pdf.drawString(col_x[idx], y, header)
    y -= 12
    pdf.setFont("Helvetica", 8)

    for row in data.interruptions:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 8)

        reseau = row.feeder_code or row.libelle_reseau or "-"
        pdf.drawString(col_x[0], y, str(row.numero_interruption))
        pdf.drawString(col_x[1], y, row.type_direction[:12])
        pdf.drawString(col_x[2], y, row.statut)
        pdf.drawString(col_x[3], y, row.date_apparition.strftime("%H:%M"))
        pdf.drawString(col_x[4], y, str(reseau)[:28])
        pdf.drawString(col_x[5], y, f"{row.end_mwh:.4f}")
        pdf.drawString(col_x[6], y, str(row.nombre_clients or "-"))
        y -= 11

    if data.feeders:
        y -= 10
        if y < 80:
            pdf.showPage()
            y = height - 40
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, y, "Feeders impactés")
        y -= 14
        pdf.setFont("Helvetica", 8)
        for feeder in data.feeders[:20]:
            pdf.drawString(
                40,
                y,
                f"{feeder.code} — {feeder.libelle} : {feeder.nombre_interruptions} int., "
                f"{feeder.end_mwh:.4f} MWh",
            )
            y -= 11
            if y < 40:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Helvetica", 8)

    pdf.showPage()
    pdf.save()


def export_mensuel_distribution_pdf(path: Path, data: MensuelDistributionReportData) -> None:
    pdf = canvas.Canvas(str(path), pagesize=landscape(A4))
    height = landscape(A4)[1]
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(
        40,
        y,
        f"Rapport mensuel distribution — {data.mois:02d}/{data.annee}",
    )
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Périmètre : {_mensuel_scope_label(data)}")
    y -= 14
    pdf.drawString(
        40,
        y,
        f"END : {data.end.aggregate.end_mwh:.4f} MWh · "
        f"SAIFI : {data.saifi.aggregate.saifi:.4f} · "
        f"SAIDI : {data.saidi.aggregate.saidi:.4f}",
    )
    y -= 14
    pdf.drawString(
        40,
        y,
        f"Interruptions : {data.end.aggregate.nombre_interruptions} · "
        f"Clients réf. : {data.saifi.aggregate.total_clients_reference}",
    )
    y -= 14
    pdf.drawString(40, y, "Template placeholder CRSE — validation SAQS requise.")
    y -= 24

    if data.end.services and data.end.services.items:
        pdf.setFont("Helvetica-Bold", 9)
        headers = ["Service", "END (MWh)", "Interruptions", "SAIFI", "SAIDI"]
        col_x = [40, 120, 220, 320, 420]
        for idx, header in enumerate(headers):
            pdf.drawString(col_x[idx], y, header)
        y -= 12
        pdf.setFont("Helvetica", 8)

        saifi_by_service = {
            item.service_id: item.saifi for item in (data.saifi.services.items if data.saifi.services else [])
        }
        saidi_by_service = {
            item.service_id: item.saidi for item in (data.saidi.services.items if data.saidi.services else [])
        }

        for item in data.end.services.items:
            if y < 40:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Helvetica", 8)
            pdf.drawString(col_x[0], y, str(item.service_id))
            pdf.drawString(col_x[1], y, f"{item.end_mwh:.4f}")
            pdf.drawString(col_x[2], y, str(item.nombre_interruptions))
            pdf.drawString(col_x[3], y, f"{saifi_by_service.get(item.service_id, 0.0):.4f}")
            pdf.drawString(col_x[4], y, f"{saidi_by_service.get(item.service_id, 0.0):.4f}")
            y -= 11

    if data.top_feeders.items:
        y -= 10
        if y < 80:
            pdf.showPage()
            y = height - 40
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, y, f"Top feeders END (top {data.top_feeders_limit})")
        y -= 14
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(40, y, "Rang")
        pdf.drawString(80, y, "Code")
        pdf.drawString(140, y, "Libellé")
        pdf.drawString(360, y, "END (MWh)")
        pdf.drawString(450, y, "Interruptions")
        y -= 11
        pdf.setFont("Helvetica", 8)
        for rank, feeder in enumerate(data.top_feeders.items, start=1):
            if y < 40:
                pdf.showPage()
                y = height - 40
                pdf.setFont("Helvetica", 8)
            pdf.drawString(40, y, str(rank))
            pdf.drawString(80, y, feeder.code[:16])
            pdf.drawString(140, y, feeder.libelle[:40])
            pdf.drawString(360, y, f"{feeder.end_mwh:.4f}")
            pdf.drawString(450, y, str(feeder.nombre_interruptions))
            y -= 11

    pdf.showPage()
    pdf.save()


def export_mensuel_transport_pdf(path: Path, data: MensuelTransportReportData) -> None:
    pdf = canvas.Canvas(str(path), pagesize=landscape(A4))
    height = landscape(A4)[1]
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(
        40,
        y,
        f"Rapport mensuel transport HTB — {data.mois:02d}/{data.annee}",
    )
    y -= 20
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, "Périmètre : National HTB")
    y -= 14
    pdf.drawString(
        40,
        y,
        f"Interruptions : {data.nombre_interruptions} · END cumulée : {data.end_cumulee_mwh:.4f} MWh",
    )
    y -= 14
    pdf.drawString(40, y, "Template placeholder CRSE — validation SAQS requise.")
    y -= 24

    pdf.setFont("Helvetica-Bold", 9)
    headers = ["N°", "Type", "Statut", "Apparition", "Équipement", "Source", "END (MWh)"]
    col_x = [40, 80, 130, 190, 270, 400, 520]
    for idx, header in enumerate(headers):
        pdf.drawString(col_x[idx], y, header)
    y -= 12
    pdf.setFont("Helvetica", 8)

    for row in data.interruptions:
        if y < 40:
            pdf.showPage()
            y = height - 40
            pdf.setFont("Helvetica", 8)
        pdf.drawString(col_x[0], y, str(row.numero_interruption))
        pdf.drawString(col_x[1], y, row.type_direction[:10])
        pdf.drawString(col_x[2], y, row.statut)
        pdf.drawString(col_x[3], y, row.date_apparition.strftime("%d/%m %H:%M"))
        pdf.drawString(col_x[4], y, (row.equipement_code or "-")[:18])
        pdf.drawString(col_x[5], y, (row.source_libelle or "-")[:20])
        pdf.drawString(col_x[6], y, f"{row.end_mwh:.4f}")
        y -= 11

    if data.top_equipements:
        y -= 10
        if y < 80:
            pdf.showPage()
            y = height - 40
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(40, y, f"Top équipements END (top {data.top_equipements_limit})")
        y -= 14
        pdf.setFont("Helvetica", 8)
        for rank, eq in enumerate(data.top_equipements, start=1):
            if y < 40:
                pdf.showPage()
                y = height - 40
            pdf.drawString(
                40,
                y,
                f"{rank}. {eq.code} — {eq.libelle} : {eq.nombre_interruptions} int., "
                f"{eq.end_mwh:.4f} MWh",
            )
            y -= 11

    pdf.showPage()
    pdf.save()


def export_annuel_pdf(path: Path, data: AnnuelReportData) -> None:
    pdf = canvas.Canvas(str(path), pagesize=landscape(A4))
    height = landscape(A4)[1]
    y = height - 40

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, f"Rapport annuel {data.annee} — {data.direction}")
    y -= 20
    pdf.setFont("Helvetica", 10)
    if data.region_id is not None:
        pdf.drawString(40, y, f"Région : {data.region_id}")
        y -= 14
    pdf.drawString(40, y, f"END totale année : {data.total_end_annee:.4f} MWh")
    y -= 14
    pdf.drawString(40, y, data.objectifs_note)
    y -= 14
    pdf.drawString(40, y, "Template placeholder CRSE — validation SAQS requise.")
    y -= 24

    if data.serie_civile:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(40, y, "Série mensuelle (année civile)")
        y -= 12
        pdf.setFont("Helvetica", 8)
        for point in data.serie_civile:
            line = f"M{point.mois:02d} — END {point.end_mwh:.4f} MWh"
            if point.saifi is not None:
                line += f" · SAIFI {point.saifi:.4f} · SAIDI {point.saidi:.4f}"
            pdf.drawString(40, y, line)
            y -= 10
            if y < 40:
                pdf.showPage()
                y = height - 40

    if data.transport_serie:
        y -= 8
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(40, y, "Transport HTB — série mensuelle")
        y -= 12
        pdf.setFont("Helvetica", 8)
        for point in data.transport_serie:
            pdf.drawString(40, y, f"M{point.mois:02d} — END {point.end_mwh:.4f} MWh")
            y -= 10

    if data.top_feeders:
        y -= 8
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(40, y, f"Top feeders END annuel (top {data.top_limit})")
        y -= 12
        pdf.setFont("Helvetica", 8)
        for rank, feeder in enumerate(data.top_feeders, start=1):
            pdf.drawString(
                40,
                y,
                f"{rank}. {feeder.code} — {feeder.libelle} : {feeder.end_mwh:.4f} MWh",
            )
            y -= 10

    if data.top_equipements:
        y -= 8
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(40, y, f"Top équipements END annuel (top {data.top_limit})")
        y -= 12
        pdf.setFont("Helvetica", 8)
        for rank, eq in enumerate(data.top_equipements, start=1):
            pdf.drawString(
                40,
                y,
                f"{rank}. {eq.code} — {eq.libelle} : {eq.end_mwh:.4f} MWh",
            )
            y -= 10

    pdf.showPage()
    pdf.save()


def write_placeholder_pdf(path: Path, *, title: str, subtitle: str) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(72, 800, title)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(72, 775, subtitle)
    pdf.drawString(72, 755, "Template placeholder CRSE — validation SAQS requise.")
    pdf.showPage()
    pdf.save()
