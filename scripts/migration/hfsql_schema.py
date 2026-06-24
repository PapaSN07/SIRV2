"""Colonnes HFSQL par table — évite SELECT * et listes trop longues (décalage ODBC pypyodbc).

Constat juin 2026 (srv-hfsql / SIR_ALHDL) :
- ``SELECT *`` ou SELECT > ~40 colonnes → valeurs décalées ;
- SELECT minimal (~30 colonnes ETL) → données correctes.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

MIGRATION_ROOT = Path(__file__).resolve().parent
REPO_ROOT = MIGRATION_ROOT.parents[1]
SIR_SQL_PATH = REPO_ROOT / "SIR.sql"
SCHEMA_CACHE_DIR = MIGRATION_ROOT / "schema_cache"

logger = logging.getLogger(__name__)

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+\[(?P<table>[^\]]+)\]\s*\((?P<body>.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]", re.MULTILINE)

# Colonnes utiles ETL — validées ODBC (pas de décalage).
INTERRUPTION_ETL_COLUMNS: list[str] = [
    "NInterruption",
    "NumeroInterruption",
    "Num",
    "EtatTraitement",
    "Validation",
    "DateApparition",
    "heureApparition",
    "Creation",
    "Modification",
    "DateSaisie",
    "Annee",
    "DateRemise",
    "heureremise",
    "DateFinRemise",
    "DateDebutDeclenchement",
    "DebutTronconn",
    "regions",
    "idservice",
    "idfeeder",
    "idcauses",
    "idsieges",
    "idsignalisation",
    "idnature",
    "Service",
    "Login",
    "Feeder",
    "Feeder1",
    "feeder2",
    "PosteSource",
    "Cause",
    "causepresumees",
    "causeeffective",
    "Sieges",
    "Signalisation",
    "Nature",
    "DureeInterruption",
    "PuissanceCoupee",
    "ENDD",
    "casforcemajeur",
    "Nombreclientimpacte",
    "NomTroncon",
    "Observation",
    "TensionPrimaire",
]

# Colonnes FK uniquement — backfill (< 25 colonnes, pas de décalage ODBC).
INTERRUPTION_FK_ETL_COLUMNS: list[str] = [
    "NInterruption",
    "regions",
    "idservice",
    "idfeeder",
    "idcauses",
    "idsieges",
    "idsignalisation",
    "idnature",
    "Service",
    "Feeder",
    "Feeder1",
    "feeder2",
    "Cause",
    "causepresumees",
    "causeeffective",
    "Sieges",
    "Signalisation",
    "Nature",
]

# Colonnes absentes sur certaines tables HFSQL (erreur SQL native).
_FK_COLUMNS_OMIT: dict[str, frozenset[str]] = {
    "Interruptions_Histo": frozenset({"idservice"}),
    "InterruptionsTransport": frozenset({"idservice", "idfeeder"}),
    "Interruptions_OMVG": frozenset({"idfeeder"}),
}


def fk_columns_for_table(table: str) -> list[str]:
    omit = _FK_COLUMNS_OMIT.get(table, frozenset())
    return [c for c in INTERRUPTION_FK_ETL_COLUMNS if c not in omit]


POSTE_INTERRUPTION_ETL_COLUMNS: list[str] = [
    "IDPosteInterruption",
    "NInterruption",
    "IDPostes",
    "Posteconcerne",
    "nombreclientposteEstime",
]

ENERGIE_ND_ETL_COLUMNS: list[str] = [
    "IDEnergieND",
    "NInterruption",
    "IDTypeEND",
    "ENDD",
    "PuissanceCoupee",
    "DureeInterruption",
    "dureeHeure",
    "casforcemajeur",
]

# Feeders — 7 colonnes validées ODBC (SELECT complet → idfeeder=0 décalé).
FEEDER_ETL_COLUMNS: list[str] = [
    "IDFeeder",
    "Feeder",
    "Service",
    "IDPosteSource",
    "PosteSource",
    "TensionPrimaire",
    "Region",
]

POSTE_SOURCE_ETL_COLUMNS: list[str] = [
    "IDPosteSource",
    "PosteSource",
]

# Troncon — 5 colonnes (table HFSQL singulier, pas Troncons).
TRONCON_ETL_COLUMNS: list[str] = [
    "IDTroncon",
    "Libelle_Troncon",
    "IDNoeudAmont",
    "IDNoeudAval",
    "IDFeeder",
]

INTERRUPTION_TRANSPORT_ETL_COLUMNS: list[str] = [
    "NInterruption",
    "Num",
    "EtatTraitement",
    "indicateurvalidation",
    "DateApparition",
    "heureApparition",
    "Creation",
    "Modification",
    "DateSaisie",
    "Annee",
    "DateRemise",
    "heureremise",
    "DateFinRemise",
    "DateDebutDeclenchement",
    "DebutTronconn",
    "regions",
    "idservice",
    "idfeeder",
    "idcauses",
    "idsieges",
    "idsignalisation",
    "idnature",
    "Service",
    "Login",
    "Feeder",
    "Feeder1",
    "feeder2",
    "PosteSource",
    "Cause",
    "causepresumees",
    "causeeffective",
    "Sieges",
    "Signalisation",
    "Nature",
    "DureeInterruption",
    "PuissanceCoupee",
    "ENDD",
    "casforcemajeur",
    "Nombreclientimpacte",
    "NomTroncon",
    "Observation",
    "TensionPrimaire",
]

MIGRATION_COLUMNS: dict[str, list[str]] = {
    "Interruptions": INTERRUPTION_ETL_COLUMNS,
    "Interruptions_Histo": INTERRUPTION_ETL_COLUMNS,
    "InterruptionsTransport": INTERRUPTION_TRANSPORT_ETL_COLUMNS,
    "Interruptions_OMVG": INTERRUPTION_ETL_COLUMNS,
    "PosteInterruption": POSTE_INTERRUPTION_ETL_COLUMNS,
    "PosteInterruption_Histo": POSTE_INTERRUPTION_ETL_COLUMNS,
    "EnergieND": ENERGIE_ND_ETL_COLUMNS,
    "Feeders": FEEDER_ETL_COLUMNS,
    "PostesSources": POSTE_SOURCE_ETL_COLUMNS,
    "Troncon": TRONCON_ETL_COLUMNS,
}

# Tables volumineuses — jamais SELECT * ni liste complète 115 colonnes.
EXPLICIT_SELECT_TABLES = frozenset(MIGRATION_COLUMNS)


@lru_cache
def _columns_from_sir_sql() -> dict[str, list[str]]:
    if not SIR_SQL_PATH.is_file():
        return {}
    text = SIR_SQL_PATH.read_text(encoding="utf-8", errors="replace")
    tables: dict[str, list[str]] = {}
    for match in _CREATE_TABLE_RE.finditer(text):
        table = match.group("table")
        body = match.group("body")
        cols = _COLUMN_RE.findall(body)
        if cols:
            tables[table] = cols
    return tables


def _cache_path(table: str) -> Path:
    return SCHEMA_CACHE_DIR / f"{table}.json"


def load_cached_columns(table: str) -> list[str] | None:
    path = _cache_path(table)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cols = data.get("columns")
        return list(cols) if cols else None
    except (json.JSONDecodeError, TypeError):
        return None


def save_cached_columns(table: str, columns: list[str], *, source: str = "odbc") -> None:
    SCHEMA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"table": table, "source": source, "columns": columns}
    _cache_path(table).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def discover_columns(conn, table: str) -> list[str]:
    """Découvre les noms ODBC via SELECT TOP 1 * (référence uniquement)."""
    cur = conn.cursor()
    cur.execute(f"SELECT TOP 1 * FROM {table}")
    columns = [col[0] for col in cur.description]
    if not columns:
        raise RuntimeError(f"Aucune colonne découverte pour {table}")
    save_cached_columns(table, columns, source="odbc_full")
    logger.info("Schéma ODBC complet mis en cache pour %s (%d colonnes)", table, len(columns))
    return columns


def get_table_columns(table: str, conn=None) -> list[str] | None:
    """Colonnes pour SELECT explicite : liste ETL minimale > cache ODBC > SIR.sql."""
    if table in MIGRATION_COLUMNS:
        return MIGRATION_COLUMNS[table]
    cached = load_cached_columns(table)
    if cached:
        return cached
    if conn is not None:
        try:
            return discover_columns(conn, table)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Découverte ODBC échouée pour %s: %s", table, str(exc)[:120])
    return _columns_from_sir_sql().get(table)


def build_select_sql(table: str, conn=None) -> str:
    """Construit SELECT avec colonnes ETL minimales (tables interruption) ou explicites."""
    columns = get_table_columns(table, conn=conn)
    if columns:
        return f"SELECT {','.join(columns)} FROM {table}"
    if table in EXPLICIT_SELECT_TABLES:
        logger.warning("Pas de colonnes ETL pour %s — SELECT * (risque décalage).", table)
    return f"SELECT * FROM {table}"


def refresh_schema_cache(conn, tables: list[str] | None = None) -> dict[str, int]:
    """Enregistre les listes ETL (ou ODBC complet pour tables sans mapping)."""
    tables = tables or sorted(EXPLICIT_SELECT_TABLES)
    result: dict[str, int] = {}
    for table in tables:
        cols = get_table_columns(table, conn=conn)
        if cols:
            save_cached_columns(table, cols, source="etl_minimal" if table in MIGRATION_COLUMNS else "odbc")
            result[table] = len(cols)
        else:
            result[table] = -1
    return result
