"""Filtre interruptions migration — fenêtre de dates + actives."""

from __future__ import annotations

from datetime import datetime, timedelta

from scripts.migration.config import MigrationSettings
from scripts.migration.transforms.dates import resolve_interruption_date_apparition
from scripts.migration.transforms.rows import row_get
from scripts.migration.transforms.statut import map_statut

CLOSED_STATUTS = frozenset({"cloture", "valide", "archive"})


def parse_migration_datetime(value: str) -> datetime:
    raw = value.strip()
    for fmt, size in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10), ("%d/%m/%Y", 10)):
        try:
            return datetime.strptime(raw[:size], fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(raw.replace("Z", ""))


def interruption_date_window(settings: MigrationSettings) -> tuple[datetime, datetime]:
    """Borne basse / haute pour l'import interruptions.

    Priorité : ``MIGRATION_DATE_FROM`` / ``MIGRATION_DATE_TO`` si définis,
    sinon fenêtre glissante ``MIGRATION_CUTOFF_YEARS``.
    """
    if settings.migration_date_from:
        date_from = parse_migration_datetime(settings.migration_date_from)
        date_from = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        date_from = datetime.now() - timedelta(days=365 * settings.migration_cutoff_years)

    if settings.migration_date_to:
        date_to = parse_migration_datetime(settings.migration_date_to)
        date_to = date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        date_to = datetime.now()

    return date_from, date_to


def date_in_window(date_app: datetime | None, date_from: datetime, date_to: datetime) -> bool:
    if date_app is None:
        return False
    return date_from <= date_app <= date_to


def should_include_interruption(
    row: dict,
    date_from: datetime,
    date_to: datetime,
    *,
    is_histo: bool,
) -> bool:
    """Inclure si date dans la fenêtre, ou encore active (hors historique)."""
    date_app = resolve_interruption_date_apparition(row)
    if date_in_window(date_app, date_from, date_to):
        return True
    if is_histo:
        return False
    statut = map_statut(
        row_get(row, "EtatTraitement"),
        row_get(row, "Validation", "indicateurvalidation"),
        is_histo,
    )
    return statut not in CLOSED_STATUTS
