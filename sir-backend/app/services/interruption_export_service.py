"""Export Excel / PDF de la liste des interruptions distribution (filtres de l'écran)."""

from __future__ import annotations

import io
from datetime import datetime

from app.schemas.interruption_distribution import InterruptionDistributionResponse

# Plafond d'une extraction synchrone : au-delà, filtrer davantage (période, région…)
MAX_LIGNES_EXPORT = 5000

_STATUTS = {"en_cours": "En cours", "cloture": "Clôturée", "valide": "Validée", "archive": "Archivée"}

# Colonnes et ordre de la liste SIR v1 (export du 19/11/2026), sans les identifiants techniques
COLONNES = [
    "N°",
    "Service Distribution",
    "Date",
    "Source",
    "Tension primaire",
    "Feeder",
    "Nature présumée",
    "Cause présumée",
    "Siège présumé",
    "Signalisation",
    "Date d'apparition",
    "Date de remise",
    "Durée",
    "Puissance coupée (kW)",
    "END (kWh)",
    "Tronçons",
    "Observation",
    "Matricule",
    "Prénom",
    "Nom",
    "Etat",
    "Régions",
    "Type END",
    "Entreprise",
    "Prestataire",
    "Validation",
    "A Modifier",
    "Date Interpellation PDM",
    "Date Arrivée PDM",
]
_LARGEURS = [9, 14, 11, 20, 9, 22, 15, 24, 16, 16, 17, 17, 9, 11, 11, 30, 30, 10, 18, 14, 8, 10, 24, 18, 18, 11, 9, 17, 17]


def _date(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y %H:%M") if value else ""


def _duree(minutes: int | None) -> str:
    if minutes is None:
        return ""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _kilo(valeur: float | None, decimales: int) -> float | None:
    """MW → kW, MWh → kWh (unités de SIR v1)."""
    return round(valeur * 1000, decimales) if valeur is not None else None


def ligne(item: InterruptionDistributionResponse) -> list[object]:
    return [
        item.numero_interruption,
        item.service_libelle or "",
        item.date_apparition.strftime("%d/%m/%Y"),
        item.poste_source_libelle or "",
        item.tension_kv,
        item.feeder_libelle or "",
        item.nature_libelle or "",
        item.cause_libelle or "",
        item.siege_libelle or "",
        item.signalisation_libelle or "",
        _date(item.date_apparition),
        _date(item.date_remise),
        _duree(item.duree_minutes),
        _kilo(item.puissance_coupee_mw, 0),
        _kilo(item.end_mwh, 2),
        item.localisation or "",
        item.observations or "",
        item.saisi_par_matricule or "",
        item.saisi_par_prenom or "",
        item.saisi_par_nom or "",
        "Fermé" if item.date_remise else "Ouvert",
        item.region_libelle or "",
        item.type_end_libelle or "",
        item.entreprise_libelle or "",
        item.prestataire_libelle or "",
        _STATUTS.get(item.statut, item.statut),
        "Oui" if item.a_modifier else "Non",
        _date(item.date_interpellation_pdm),
        _date(item.date_arrivee_pdm),
    ]


def construire_xlsx(items: list[InterruptionDistributionResponse], filtres: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Interruptions"
    ws.append([f"SIR — Interruptions distribution · {filtres}"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([f"Extraction du {datetime.now():%d/%m/%Y %H:%M} · {len(items)} ligne(s)"])
    ws.append([])
    ws.append(COLONNES)
    for cell in ws[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3C1053")
    for item in items:
        ws.append(ligne(item))
    for i, largeur in enumerate(_LARGEURS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largeur
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = f"A4:{get_column_letter(len(COLONNES))}{4 + len(items)}"
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def construire_pdf(items: list[InterruptionDistributionResponse], filtres: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24
    )
    styles = getSampleStyleSheet()
    # Colonnes utiles à la lecture papier (le détail complet est dans l'export Excel)
    entetes = ["N°", "Statut", "Apparition", "Remise", "Durée", "Service", "Feeder", "Cause", "END (MWh)"]
    data = [entetes]
    for item in items:
        data.append(
            [
                str(item.numero_interruption),
                _STATUTS.get(item.statut, item.statut),
                _date(item.date_apparition),
                _date(item.date_remise),
                f"{item.duree_minutes} min" if item.duree_minutes is not None else "",
                (item.service_libelle or "")[:28],
                (item.feeder_libelle or "")[:22],
                (item.cause_libelle or "")[:28],
                f"{item.end_mwh:.2f}".replace(".", ",") if item.end_mwh is not None else "",
            ]
        )
    table = Table(data, repeatRows=1, colWidths=[52, 58, 80, 80, 50, 140, 110, 150, 60])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3C1053")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3EEF8")]),
                ("ALIGN", (8, 1), (8, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D4C8DE")),
            ]
        )
    )
    doc.build(
        [
            Paragraph("SIR — Interruptions distribution", styles["Title"]),
            Paragraph(f"{filtres} · {len(items)} ligne(s) · extraction du {datetime.now():%d/%m/%Y %H:%M}", styles["Normal"]),
            Spacer(1, 8),
            table,
        ]
    )
    return buffer.getvalue()
