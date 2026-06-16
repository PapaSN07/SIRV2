"""Façade export rapports — délègue aux services PDF / Excel (Sprint 6)."""

from datetime import date
from pathlib import Path

from app.services import rapport_export_excel_service as xlsx_svc
from app.services import rapport_export_pdf_service as pdf_svc
from app.services.rapport_annuel_service import AnnuelReportData
from app.services.rapport_journalier_service import JournalierReportData
from app.services.rapport_mensuel_service import MensuelDistributionReportData
from app.services.rapport_mensuel_transport_service import MensuelTransportReportData


def export_journalier(path: Path, *, format: str, data: JournalierReportData) -> None:
    if format == "xlsx":
        xlsx_svc.export_journalier_xlsx(path, data)
    else:
        pdf_svc.export_journalier_pdf(path, data)


def export_mensuel_distribution(
    path: Path,
    *,
    format: str,
    data: MensuelDistributionReportData,
) -> None:
    if format == "xlsx":
        xlsx_svc.export_mensuel_distribution_xlsx(path, data)
    else:
        pdf_svc.export_mensuel_distribution_pdf(path, data)


def export_mensuel_transport(
    path: Path,
    *,
    format: str,
    data: MensuelTransportReportData,
) -> None:
    if format == "xlsx":
        xlsx_svc.export_mensuel_transport_xlsx(path, data)
    else:
        pdf_svc.export_mensuel_transport_pdf(path, data)


def export_annuel(path: Path, *, format: str, data: AnnuelReportData) -> None:
    if format == "xlsx":
        xlsx_svc.export_annuel_xlsx(path, data)
    else:
        pdf_svc.export_annuel_pdf(path, data)


def generate_placeholder_file(
    path: Path,
    *,
    format: str,
    type_rapport: str,
    report_date: date | None,
) -> None:
    date_label = report_date.isoformat() if report_date else "N/A"
    title = f"Rapport SIR — {type_rapport}"
    subtitle = f"Période : {date_label}"

    if format == "xlsx":
        xlsx_svc.write_placeholder_xlsx(path, title=title, subtitle=subtitle)
    else:
        pdf_svc.write_placeholder_pdf(path, title=title, subtitle=subtitle)
