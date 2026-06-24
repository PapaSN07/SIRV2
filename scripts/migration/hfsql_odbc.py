"""Connexion ODBC HFSQL — pyodbc avec repli pypyodbc et lecture JSONL."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from scripts.migration.config import get_settings
from scripts.migration.hfsql_schema import build_select_sql, get_table_columns
from scripts.migration.transforms.rows import wrap_row

logger = logging.getLogger(__name__)


def _pick_odbc_module():
    """pypyodbc en priorité — pyodbc provoque des crashes avec le driver HFSQL PC SOFT."""
    try:
        import pypyodbc as pyodbc  # noqa: PLC0415

        _patch_pypyodbc_date_parser(pyodbc)
        return pyodbc, "pypyodbc"
    except ImportError:
        pass
    try:
        import pyodbc  # noqa: PLC0415

        return pyodbc, "pyodbc"
    except ImportError as exc:
        raise RuntimeError(
            "Installez pypyodbc (recommandé) ou pyodbc pour accéder à HFSQL."
        ) from exc


_DATE_ONLY_FORMATS = frozenset({"%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"})
_TEMPORAL_FORMATS = (
    "%Y%m%d%H%M%S",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
)
_TIME_FORMATS = ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M")


def parse_hfsql_temporal(value: Any, kind: str) -> Any:
    """Convertit une valeur temporelle HFSQL brute en date/datetime/time Python.

    Le driver HFSQL PC SOFT renvoie les colonnes Date au format compact
    ``YYYYMMDD`` (ex ``b'20240118'``) et les valeurs vides comme ``0000-00-00``
    ou des suites de zéros. ``kind`` ∈ {"date", "datetime", "time"}.
    """
    if value is None or isinstance(value, (datetime, date, time)):
        return value
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="replace")
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None

    if kind == "time":
        for fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(raw, fmt).time()
            except ValueError:
                continue
        return None

    # Date/heure vide HFSQL : uniquement des zéros (ex 00000000, 0000-00-00 00:00:00).
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits or set(digits) <= {"0"}:
        return None

    for fmt in _TEMPORAL_FORMATS:
        try:
            parsed = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if kind == "date" and fmt in _DATE_ONLY_FORMATS:
            return parsed.date()
        return parsed

    try:
        return datetime.fromisoformat(raw.replace("Z", ""))
    except ValueError:
        return None


def _patch_pypyodbc_date_parser(pyodbc_module) -> None:
    """Remplace les convertisseurs date/heure HFSQL par un parseur robuste.

    Le convertisseur natif pypyodbc attend ``YYYY-MM-DD`` et lève ``ValueError``
    sur le format compact HFSQL ``YYYYMMDD`` — sans patch la lecture plante, et
    l'ancien patch silencieux (try/except → None) faisait perdre toutes les dates
    compactes, donc les interruptions 2023+ (DateApparition renseignée mais
    Creation = 0000-00-00).
    """
    if getattr(pyodbc_module, "_sir_date_patch", False):
        return

    type_dict = pyodbc_module.SQL_data_type_dict

    def _make(kind: str):  # type: ignore[no-untyped-def]
        def cvt(value):
            return parse_hfsql_temporal(value, kind)

        return cvt

    by_kind = {
        "date": (pyodbc_module.SQL_DATE, pyodbc_module.SQL_TYPE_DATE),
        "datetime": (pyodbc_module.SQL_TIMESTAMP, pyodbc_module.SQL_TYPE_TIMESTAMP),
        "time": (
            pyodbc_module.SQL_TIME,
            getattr(pyodbc_module, "SQL_SS_TIME2", None),
            pyodbc_module.SQL_TYPE_TIME,
        ),
    }
    for kind, sql_types in by_kind.items():
        for sql_type in sql_types:
            if sql_type is None or sql_type not in type_dict:
                continue
            entry = type_dict[sql_type]
            type_dict[sql_type] = (entry[0], _make(kind), *entry[2:])

    pyodbc_module._sir_date_patch = True


def build_connection_string() -> str:
    s = get_settings()
    if s.hfsql_dsn:
        parts = [f"DSN={s.hfsql_dsn}", f"UID={s.hfsql_user}", f"PWD={s.hfsql_password}"]
        return ";".join(parts)
    return (
        f"DRIVER={{{s.hfsql_driver}}};"
        f"Server Name={s.hfsql_server};"
        f"Server Port={s.hfsql_port};"
        f"Database={s.hfsql_database};"
        f"UID={s.hfsql_user};"
        f"PWD={s.hfsql_password};"
        f"IntegrityCheck=1"
    )


def connect_hfsql(timeout: int = 30):
    pyodbc, backend = _pick_odbc_module()
    conn_str = build_connection_string()
    logger.info("Connexion HFSQL via %s (%s)", backend, conn_str.split("PWD=")[0])
    return pyodbc.connect(conn_str, timeout=timeout)


def test_connection() -> dict[str, Any]:
    """Teste la connectivité et retourne des counts sur tables P0."""
    tables = ["Interruptions", "Utilisateurs", "Feeders"]
    result: dict[str, Any] = {
        "connection_string_prefix": build_connection_string().split("PWD=")[0],
        "connected": False,
        "server_reachable": False,
        "tables": {},
        "error": None,
    }
    try:
        conn = connect_hfsql(timeout=15)
        result["server_reachable"] = True
        cur = conn.cursor()
        result["connected"] = True
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row = cur.fetchone()
                result["tables"][table] = int(row[0]) if row else None
            except Exception as exc:  # noqa: BLE001
                result["tables"][table] = {"error": str(exc)[:200]}
        conn.close()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        result["error"] = msg[:500]
        if "srv-hfsql" in msg:
            result["server_reachable"] = True
    return result


def _serialize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def fetch_all(conn, query: str, params: tuple | None = None) -> list[dict[str, Any]]:
    return list(iter_fetch(conn, query, params))


def _row_to_dict(columns: list[str], row: tuple) -> dict[str, Any]:
    values = list(row)
    if len(values) < len(columns):
        values.extend([None] * (len(columns) - len(values)))
    elif len(values) > len(columns):
        values = values[: len(columns)]
    return wrap_row({col: _serialize_value(val) for col, val in zip(columns, values, strict=True)})


def iter_fetch(conn, query: str, params: tuple | None = None) -> Iterator[dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(query, params or ())
    columns = [col[0] for col in cur.description]
    for row in cur.fetchall():
        yield _row_to_dict(columns, row)


def fetch_table(conn, table: str) -> Iterator[dict[str, Any]]:
    """Itère une table HFSQL avec SELECT explicite (colonnes ODBC en cache)."""
    return iter_fetch(conn, build_select_sql(table, conn=conn))


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield wrap_row(json.loads(line))


# Exports PosteInterruption non filtrés (>50 Mo) — ignorer, requête HFSQL ciblée à la place.
_OVERSIZED_EXPORT_BYTES = 50 * 1024 * 1024
_OVERSIZED_EXPORT_TABLES = frozenset({"PosteInterruption", "PosteInterruption_Histo"})


def export_meta(table: str, exports_dir: Path | None = None) -> dict[str, Any]:
    s = get_settings()
    exports_dir = exports_dir or s.exports_dir
    meta_path = exports_dir / f"{table}.meta.json"
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def export_is_pre_filtered(table: str, exports_dir: Path | None = None) -> bool:
    meta = export_meta(table, exports_dir)
    filt = meta.get("filter")
    return bool(filt and filt != "none")


def _should_skip_export(table: str, jsonl_path: Path) -> bool:
    if table not in _OVERSIZED_EXPORT_TABLES:
        return False
    if not jsonl_path.is_file():
        return False
    if jsonl_path.stat().st_size > _OVERSIZED_EXPORT_BYTES:
        logger.warning(
            "Export %s trop volumineux (%d Mo) — lecture HFSQL ciblée.",
            table,
            jsonl_path.stat().st_size // (1024 * 1024),
        )
        return True
    return False


def iter_table_rows(
    table: str, exports_dir: Path | None = None, allow_live: bool = True
) -> Iterator[dict[str, Any]]:
    """Itère les lignes d'une table (JSONL export ou HFSQL live)."""
    s = get_settings()
    exports_dir = exports_dir or s.exports_dir
    jsonl_path = exports_dir / f"{table}.jsonl"
    if jsonl_path.exists() and not _should_skip_export(table, jsonl_path):
        yield from iter_jsonl(jsonl_path)
        return
    if not allow_live:
        return
    try:
        conn = connect_hfsql()
        try:
            yield from fetch_table(conn, table)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Table %s indisponible: %s", table, str(exc)[:120])


def fetch_poste_interruptions_live(
    table: str, interruption_ids: list[int], *, chunk_size: int = 200
) -> Iterator[dict[str, Any]]:
    """Charge PosteInterruption pour un sous-ensemble d'interruptions (évite 16M lignes)."""
    if not interruption_ids:
        return
    columns = get_table_columns(table)
    if not columns:
        logger.warning("Pas de colonnes ETL pour %s", table)
        return
    cols_sql = ",".join(columns)
    conn = connect_hfsql()
    try:
        for i in range(0, len(interruption_ids), chunk_size):
            chunk = interruption_ids[i : i + chunk_size]
            ids_sql = ",".join(str(int(x)) for x in chunk)
            query = f"SELECT {cols_sql} FROM {table} WHERE NInterruption IN ({ids_sql})"
            yield from iter_fetch(conn, query)
    finally:
        conn.close()


def load_table_rows(
    table: str, exports_dir: Path | None = None, allow_live: bool = True
) -> list[dict[str, Any]]:
    """Charge depuis JSONL export ou HFSQL live."""
    return list(iter_table_rows(table, exports_dir=exports_dir, allow_live=allow_live))


def write_jsonl(path: Path, rows: list[dict[str, Any]], metadata: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    meta_path = path.with_suffix(".meta.json")
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    meta = {"row_count": len(rows), "extracted_at": datetime.now().isoformat(), **(metadata or {})}
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
