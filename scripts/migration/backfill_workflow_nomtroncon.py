#!/usr/bin/env python3
"""Backfill noeuds workflow depuis interruptions.localisation (NomTroncon HFSQL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings


def _url() -> str:
    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def run(*, dry_run: bool) -> dict[str, int]:
    engine = create_engine(_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        before = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.workflows w
                INNER JOIN dbo.interruptions i ON i.id = w.interruption_id
                INNER JOIN dbo.etapes_workflow e ON e.id = w.etape_workflow_id AND e.code = 'tronconnement'
                WHERE i.localisation IS NOT NULL
                  AND LEN(LTRIM(RTRIM(i.localisation))) > 0
                  AND w.noeud_amont_libelle IS NULL
                """
            )
        ).scalar_one()
        if dry_run:
            return {"would_update": int(before)}

        result = conn.execute(
            text(
                """
                UPDATE w
                SET
                    noeud_amont_libelle = CASE
                        WHEN CHARINDEX(' - ', i.localisation) > 0 THEN
                            LEFT(
                                LTRIM(RTRIM(SUBSTRING(i.localisation, 1, CHARINDEX(' - ', i.localisation) - 1))),
                                255
                            )
                        ELSE LEFT(LTRIM(RTRIM(i.localisation)), 255)
                    END,
                    noeud_aval_libelle = CASE
                        WHEN CHARINDEX(' - ', i.localisation) > 0 THEN
                            LEFT(
                                LTRIM(RTRIM(SUBSTRING(i.localisation, CHARINDEX(' - ', i.localisation) + 3, 8000))),
                                255
                            )
                        ELSE NULL
                    END
                FROM dbo.workflows w
                INNER JOIN dbo.interruptions i ON i.id = w.interruption_id
                INNER JOIN dbo.etapes_workflow e ON e.id = w.etape_workflow_id AND e.code = 'tronconnement'
                WHERE i.localisation IS NOT NULL
                  AND LEN(LTRIM(RTRIM(i.localisation))) > 0
                  AND w.noeud_amont_libelle IS NULL
                """
            )
        )
        conn.commit()
        updated = int(result.rowcount)
    engine.dispose()
    return {"candidates": int(before), "updated": updated}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run or not args.execute
    report = run(dry_run=dry_run)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
