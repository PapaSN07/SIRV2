"""Fusion date + heure et parsing datetime legacy HFSQL."""

from __future__ import annotations

from datetime import date, datetime, time


def _is_empty(value: str | datetime | date | int | float | time | None) -> bool:
    return value is None or value == 0 or value == "" or value == "0"


def parse_time(value: str | datetime | time | None) -> time | None:
    if value is None or _is_empty(value):
        return None
    if isinstance(value, time):
        return value
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        raw = value.strip()
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(raw[: len(fmt)], fmt).time()
            except ValueError:
                continue
        parsed = parse_datetime(raw)
        return parsed.time() if parsed else None
    return None


def parse_datetime(value: str | datetime | date | int | float | time | None) -> datetime | None:
    if _is_empty(value):
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    if isinstance(value, time):
        return None
    if isinstance(value, str):
        raw = value.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
        ):
            try:
                chunk = raw[:19] if "T" in fmt or " " in fmt else raw[:10]
                return datetime.strptime(chunk, fmt[: len(chunk)] if len(chunk) < 19 else fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", ""))
        except ValueError:
            return None
    return None


def merge_date_time(
    date_val: str | datetime | date | None,
    time_val: str | datetime | time | None,
) -> datetime | None:
    d = parse_datetime(date_val)
    if _is_empty(time_val):
        return d if d and d.year >= 1980 else None
    if isinstance(time_val, datetime):
        if d is None or d.year < 1980:
            if time_val.year >= 1980:
                return time_val.replace(tzinfo=None) if time_val.tzinfo else time_val
            return None
        return datetime.combine(d.date(), time_val.time())
    if d is None or d.year < 1980:
        return None
    t = parse_time(time_val)
    if t is None:
        return d
    return datetime.combine(d.date(), t)


def duration_minutes(
    duree_field: int | float | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
) -> int | None:
    max_minutes = 525_600  # 1 an
    if duree_field is not None:
        try:
            val = int(float(duree_field))
            if 0 < val <= max_minutes:
                return val
        except (TypeError, ValueError):
            pass
    if date_debut and date_fin and date_fin >= date_debut:
        computed = int((date_fin - date_debut).total_seconds() // 60)
        if 0 < computed <= max_minutes:
            return computed
    return None


def resolve_interruption_date_apparition(row: dict) -> datetime | None:
    """Date d'apparition interruption (distribution / transport / OMVG).

    Constat srv-hfsql SIR_ALHDL (juin 2026, après correctif convertisseur ODBC) :
    - ``DateApparition`` est en réalité renseignée sur 100 % des lignes, au format
      compact HFSQL ``YYYYMMDD`` (ex ``b'20240118'``). L'ancien audit la croyait
      NULL car le convertisseur pypyodbc échouait silencieusement sur ce format ;
    - ``heureApparition`` porte l'heure (chaîne HH:MM:SS ou time ODBC) ;
    - ``Creation`` / ``Modification`` valent ``0000-00-00`` sur les lignes récentes
      (2023+) : ils ne servent que de repli pour les anciens enregistrements.

    On priorise donc ``DateApparition`` (couvre 2017→2026), avec repli sur
    ``Creation``/``Modification`` puis ``Annee``.
    """
    from scripts.migration.transforms.rows import row_get

    heure = row_get(row, "heureApparition", "heureapparition")

    # heureApparition peut parfois contenir un datetime complet
    heure_full = parse_datetime(heure)
    if heure_full and heure_full.year >= 1980:
        return heure_full

    date_candidates = (
        "DateApparition",
        "dateapparition",
        "Creation",
        "creation",
        "Modification",
        "modification",
        "DateSaisie",
        "datesaisie",
        "DateDebutDeclenchement",
        "datedebutdeclenchement",
        "DebutTronconn",
        "debuttronconn",
    )
    seen: set[str] = set()
    for field in date_candidates:
        key = field.lower()
        if key in seen:
            continue
        seen.add(key)
        date_val = row_get(row, field)
        if _is_empty(date_val):
            continue
        merged = merge_date_time(date_val, heure)
        if merged and merged.year >= 1980:
            return merged
        parsed = parse_datetime(date_val)
        if parsed and parsed.year >= 1980:
            return parsed

    # Anciens enregistrements : Annee renseignée, Creation absente
    annee_raw = row_get(row, "Annee", "annee")
    if not _is_empty(annee_raw) and not _is_empty(heure):
        try:
            year = int(annee_raw)
        except (TypeError, ValueError):
            year = 0
        if 1990 <= year <= 2100:
            t = parse_time(heure) or time.min
            return datetime(year, 1, 1, t.hour, t.minute, t.second)

    return None


def resolve_interruption_date_remise(row: dict) -> datetime | None:
    from scripts.migration.transforms.rows import row_get

    heure = row_get(row, "heureremise", "HeureRemise", "heurefinremise", "HeureFinRemise")
    heure_full = parse_datetime(heure)
    if heure_full and heure_full.year >= 1980:
        return heure_full

    for field in (
        "DateRemise",
        "dateremise",
        "DateFinRemise",
        "datefinremise",
        "DebutRemise",
        "debutremise",
        "FinLocal",
        "finlocal",
        "Modification",
        "modification",
    ):
        date_val = row_get(row, field)
        if _is_empty(date_val):
            continue
        merged = merge_date_time(date_val, heure)
        if merged and merged.year >= 1980:
            return merged
        parsed = parse_datetime(date_val)
        if parsed and parsed.year >= 1980:
            return parsed
    return None
