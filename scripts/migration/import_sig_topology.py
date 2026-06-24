#!/usr/bin/env python3
"""Import topologie SIG HFSQL (Noeud_SIG, Troncon_SIG) vers dbo.noeuds_sig / dbo.troncons_sig."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.db_session import get_session
from scripts.migration.extract_hfsql import run as run_extract
from scripts.migration.id_maps import IdMapStore
from scripts.migration.loaders.sig import SigLoader


def _counts() -> dict[str, int]:
    from sqlalchemy import create_engine, text

    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        noeuds = int(conn.execute(text("SELECT COUNT(*) FROM dbo.noeuds_sig")).scalar_one())
        troncons = int(conn.execute(text("SELECT COUNT(*) FROM dbo.troncons_sig")).scalar_one())
    return {"noeuds_sig": noeuds, "troncons_sig": troncons}


def run(*, dry_run: bool, skip_extract: bool) -> dict:
    ensure_dirs()
    report: dict = {"dry_run": dry_run, "before": _counts()}

    if not skip_extract:
        report["extract"] = run_extract(tables=["Noeud_SIG", "Troncon_SIG"])
    else:
        report["extract"] = {"skipped": True}

    id_maps = IdMapStore()
    with get_session() as session:
        loader = SigLoader(session, id_maps, dry_run=dry_run)
        loader.run()
        loader.flush_batch()
        id_maps.save("noeuds_sig")
        id_maps.save("troncons_sig")
        report["etl"] = loader.summary()

    report["after"] = _counts() if not dry_run else report["before"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--skip-extract", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute if args.execute else (args.dry_run or get_settings().migration_dry_run)
    try:
        report = run(dry_run=dry_run, skip_extract=args.skip_extract)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
