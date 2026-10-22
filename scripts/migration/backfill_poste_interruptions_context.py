#!/usr/bin/env python3
"""Backfill feeder_id / service_id / poste_source_id sur poste_interruptions.

Dénormalise depuis interruptions (+ repli postes / feeders).

Usage :
    python scripts/migration/backfill_poste_interruptions_context.py --dry-run
    python scripts/migration/backfill_poste_interruptions_context.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from sqlalchemy import create_engine, text

BACKFILL_SQL = """
UPDATE pi
SET
    feeder_id = COALESCE(pi.feeder_id, i.feeder_id, p.feeder_id),
    service_id = COALESCE(pi.service_id, i.service_id, p.service_id, f.service_id),
    poste_source_id = COALESCE(pi.poste_source_id, i.poste_source_id, f.poste_source_id)
FROM dbo.poste_interruptions AS pi
INNER JOIN dbo.interruptions AS i ON i.id = pi.interruption_id
LEFT JOIN dbo.postes AS p ON p.id = pi.poste_id
LEFT JOIN dbo.feeders AS f
    ON f.id = COALESCE(i.feeder_id, p.feeder_id, pi.feeder_id)
WHERE
    pi.feeder_id IS NULL
    OR pi.service_id IS NULL
    OR pi.poste_source_id IS NULL
"""

STATS_SQL = """
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN feeder_id IS NULL THEN 1 ELSE 0 END) AS null_feeder,
    SUM(CASE WHEN service_id IS NULL THEN 1 ELSE 0 END) AS null_service,
    SUM(CASE WHEN poste_source_id IS NULL THEN 1 ELSE 0 END) AS null_poste_source
FROM dbo.poste_interruptions
"""


def _sync_url() -> str:
    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def run(*, dry_run: bool) -> dict[str, Any]:
    ensure_dirs()
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with engine.connect() as conn:
            before = dict(conn.execute(text(STATS_SQL)).mappings().one())
            report["before"] = before
            if dry_run:
                report["would_update_where_null"] = {
                    "feeder": before["null_feeder"],
                    "service": before["null_service"],
                    "poste_source": before["null_poste_source"],
                }
                return report

            with engine.begin() as tx:
                result = tx.execute(text(BACKFILL_SQL))
                report["rowcount"] = result.rowcount
            after = dict(conn.execute(text(STATS_SQL)).mappings().one())
            report["after"] = after
    finally:
        engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill feeder/service/poste_source sur poste_interruptions"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.dry_run == args.execute:
        print("Choisir exactement --dry-run ou --execute", file=sys.stderr)
        return 2

    report = run(dry_run=args.dry_run)
    path = get_settings().reports_dir / "backfill_poste_interruptions_context.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Rapport: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
