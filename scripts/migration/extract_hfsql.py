#!/usr/bin/env python3
"""Extraction HFSQL → JSONL avec filtre 3 ans sur interruptions."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_table
from scripts.migration.interruption_filter import interruption_date_window, should_include_interruption

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _load_tables() -> list[str]:
    with get_settings().mapping_path.open(encoding="utf-8") as f:
        mapping = yaml.safe_load(f)
    tables: list[str] = []
    for domain in mapping.get("audit_tables", {}).values():
        if isinstance(domain, list):
            tables.extend(domain)
        elif isinstance(domain, dict):
            for sub in domain.values():
                tables.extend(sub)
    # Tables interruptions additionnelles
    for src in mapping.get("interruptions", {}).get("sources", []):
        tables.append(src["table"])
    for src in mapping.get("poste_interruptions", {}).get("sources", []):
        tables.append(src["table"])
    return list(dict.fromkeys(tables))


def _should_export_row(
    table: str,
    row: dict,
    date_from: datetime,
    date_to: datetime,
    is_histo: bool,
) -> bool:
    if table in ("Interruptions", "InterruptionsTransport", "Interruptions_OMVG"):
        return should_include_interruption(row, date_from, date_to, is_histo=False)
    if table == "Interruptions_Histo":
        return should_include_interruption(row, date_from, date_to, is_histo=True)
    return True


def extract_table(
    conn, table: str, date_from: datetime, date_to: datetime, out_path: Path
) -> dict:
    raw_count = 0
    exported_count = 0
    hasher = hashlib.sha256()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for row in fetch_table(conn, table):
            raw_count += 1
            if _should_export_row(
                table, row, date_from, date_to, is_histo=table == "Interruptions_Histo"
            ):
                line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
                f.write(line)
                hasher.update(line.encode("utf-8"))
                exported_count += 1
            if raw_count % 50000 == 0:
                logger.info("%s : %d lignes lues, %d exportées…", table, raw_count, exported_count)

    meta: dict = {"source_table": table, "raw_count": raw_count, "exported_count": exported_count}
    if table in ("Interruptions", "InterruptionsTransport", "Interruptions_OMVG"):
        meta["filter"] = "active_or_date_window"
        meta["date_from"] = date_from.isoformat()
        meta["date_to"] = date_to.isoformat()
    elif table == "Interruptions_Histo":
        meta["filter"] = "date_window_only"
        meta["date_from"] = date_from.isoformat()
        meta["date_to"] = date_to.isoformat()
    elif table.startswith("PosteInterruption"):
        meta["filter"] = "none"
    meta["checksum"] = hasher.hexdigest()[:16]
    meta_path = out_path.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(
            {"row_count": exported_count, "extracted_at": datetime.now().isoformat(), **meta},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return meta


def run(tables: list[str] | None = None) -> dict:
    ensure_dirs()
    settings = get_settings()
    date_from, date_to = interruption_date_window(settings)
    tables = tables or _load_tables()
    summary: dict = {
        "extracted_at": datetime.now().isoformat(),
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "tables": {},
    }

    conn = connect_hfsql()
    try:
        for table in tables:
            try:
                logger.info("Extraction %s…", table)
                out = settings.exports_dir / f"{table}.jsonl"
                meta = extract_table(conn, table, date_from, date_to, out)
                summary["tables"][table] = meta
                logger.info(
                    "OK %s : %d exportées / %d brutes",
                    table,
                    meta.get("exported_count", 0),
                    meta.get("raw_count", 0),
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Erreur %s", table)
                summary["tables"][table] = {"error": str(exc)[:200]}
    finally:
        conn.close()

    report_path = settings.reports_dir / f"extract_{datetime.now():%Y%m%d}.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary["report_path"] = str(report_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Extraction HFSQL → JSONL")
    parser.add_argument("--table", action="append", help="Extraire une table spécifique (répétable)")
    args = parser.parse_args()
    try:
        report = run(tables=args.table)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
