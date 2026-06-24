#!/usr/bin/env python3
"""Audit source HFSQL — counts, dates, doublons, orphelins (tables P0)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import yaml

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.hfsql_odbc import connect_hfsql, fetch_table, iter_jsonl, load_table_rows
from scripts.migration.transforms.dates import resolve_interruption_date_apparition
from scripts.migration.transforms.rows import row_get


def _load_mapping() -> dict:
    path = get_settings().mapping_path
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _audit_table(table: str, rows: list[dict]) -> dict:
    report: dict = {"table": table, "count": len(rows), "null_keys": {}, "duplicates": [], "date_range": {}}
    if not rows:
        return report

    # Colonnes clés selon table
    key_fields = {
        "Utilisateurs": "Login",
        "Feeders": "Feeder",
        "Interruptions": "NumeroInterruption",
        "Services": "Service",
    }
    key_field = key_fields.get(table)
    if key_field:
        values = [str(r.get(key_field) or "").strip() for r in rows]
        non_empty = [v for v in values if v]
        report["null_keys"][key_field] = round(100 * (len(values) - len(non_empty)) / len(values), 2)
        seen: dict[str, int] = {}
        for v in non_empty:
            seen[v] = seen.get(v, 0) + 1
        report["duplicates"] = [k for k, c in seen.items() if c > 1][:20]

    date_fields = [
        "DateApparition",
        "heureApparition",
        "Creation",
        "Modification",
        "DateRemise",
        "heureremise",
        "DateSaisie",
    ]
    for df in date_fields:
        dates = [row_get(r, df) for r in rows if row_get(r, df)]
        if dates:
            report["date_range"][df] = {"min": min(dates), "max": max(dates)}

    if table in ("Interruptions", "InterruptionsTransport", "Interruptions_OMVG", "Interruptions_Histo"):
        resolved = sum(1 for r in rows if resolve_interruption_date_apparition(r))
        report["date_apparition_resolved"] = {
            "count": resolved,
            "pct": round(100 * resolved / len(rows), 2) if rows else 0,
        }

    if table == "Interruptions" and rows:
        services = {str(r.get("Service") or "").strip() for r in rows}
        svc_rows = load_table_rows("Services") if table == "Interruptions" else []
        known = {str(r.get("Service") or "").strip() for r in svc_rows}
        orphan = sorted(s for s in services if s and s not in known)
        report["orphan_services"] = orphan[:20]

    if table == "Utilisateurs":
        report["plaintext_passwords"] = sum(1 for r in rows if r.get("mdp"))

    return report


def _orphan_csv(anomalies: list[dict], path: Path) -> None:
    if not anomalies:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for a in anomalies for k in a.keys()})
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(anomalies)


def run(use_exports: bool = False) -> dict:
    ensure_dirs()
    mapping = _load_mapping()
    audit_cfg = mapping.get("audit_tables", {})
    tables: list[str] = []
    for domain_tables in audit_cfg.values():
        if isinstance(domain_tables, list):
            tables.extend(domain_tables)
        elif isinstance(domain_tables, dict):
            for v in domain_tables.values():
                tables.extend(v)

    tables = list(dict.fromkeys(tables))
    results: dict = {"generated_at": datetime.now().isoformat(), "tables": {}, "anomalies": []}

    conn = None
    if not use_exports:
        try:
            conn = connect_hfsql()
        except Exception as exc:  # noqa: BLE001
            results["connection_error"] = str(exc)[:300]
            use_exports = True

    for table in tables:
        try:
            if use_exports:
                export_path = get_settings().exports_dir / f"{table}.jsonl"
                rows = list(iter_jsonl(export_path)) if export_path.exists() else []
            else:
                rows = list(fetch_table(conn, table))
            results["tables"][table] = _audit_table(table, rows)
        except Exception as exc:  # noqa: BLE001
            results["tables"][table] = {"error": str(exc)[:200]}
            results["anomalies"].append({"table": table, "type": "fetch_error", "detail": str(exc)[:200]})

    if conn:
        conn.close()

    stamp = datetime.now().strftime("%Y%m%d")
    report_path = get_settings().reports_dir / f"audit_{stamp}.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    _orphan_csv(results["anomalies"], get_settings().reports_dir / f"audit_anomalies_{stamp}.csv")
    results["report_path"] = str(report_path)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit HFSQL P0")
    parser.add_argument("--exports-only", action="store_true", help="Utiliser JSONL locaux uniquement")
    args = parser.parse_args()
    report = run(use_exports=args.exports_only)
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if "connection_error" not in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
