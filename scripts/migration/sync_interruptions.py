#!/usr/bin/env python3
"""Synchronise la table dbo.interruptions depuis HFSQL (extract + insert + update).

Usage typique (données à jour pour la liste SIRV2) :

    python scripts/migration/sync_interruptions.py --dry-run
    python scripts/migration/sync_interruptions.py --execute

Étapes :
  1. Extraction JSONL depuis HFSQL (tables interruptions)
  2. ETL sync : nouvelles lignes + mise à jour des existantes (id_maps)
  3. Backfill FK résiduelles (service, cause…)
  4. Rapport comptages SQL Server
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.interruption_filter import interruption_date_window
from scripts.migration.db_session import get_session
from scripts.migration.extract_hfsql import run as run_extract
from scripts.migration.id_maps import IdMapStore
from scripts.migration.loaders.interruptions import InterruptionsLoader

# Tables interruptions distribution à ré-extraire à chaque sync
INTERRUPTION_EXTRACT_TABLES: list[str] = [
    "Interruptions",
    "Interruptions_Histo",
]
# --avec-transport : le loader relit aussi ces exports ; sans nouvel export, il rejouerait d'anciens fichiers
TRANSPORT_EXTRACT_TABLES: list[str] = ["InterruptionsTransport", "Interruptions_OMVG", "EnergieND"]


def _sql_counts() -> dict[str, int | str]:
    from sqlalchemy import create_engine, text

    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        total = conn.execute(
            text(
                "SELECT COUNT(*) FROM dbo.interruptions WHERE type_direction = 'distribution'"
            )
        ).scalar_one()
        max_date = conn.execute(
            text(
                "SELECT MAX(date_apparition) FROM dbo.interruptions "
                "WHERE type_direction = 'distribution'"
            )
        ).scalar_one()
    return {
        "distribution_count": int(total),
        "max_date_apparition": str(max_date) if max_date else None,
    }


def run_sync(
    *,
    dry_run: bool,
    skip_extract: bool,
    skip_backfill: bool,
    update_existing: bool,
    avec_transport: bool = False,
) -> dict:
    ensure_dirs()
    settings = get_settings()
    date_from, date_to = interruption_date_window(settings)
    report: dict = {
        "started_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "update_existing": update_existing,
        "before": _sql_counts(),
    }

    if not skip_extract:
        tables = INTERRUPTION_EXTRACT_TABLES + (TRANSPORT_EXTRACT_TABLES if avec_transport else [])
        report["extract"] = run_extract(tables=tables)
    else:
        report["extract"] = {"skipped": True}

    id_maps = IdMapStore()
    with get_session() as session:
        loader = InterruptionsLoader(
            session,
            id_maps,
            dry_run=dry_run,
            sync_existing=update_existing,
            system_user_id=1,
        )
        report["etl"] = loader.run()
        loader.flush_batch()

    if not dry_run and not skip_backfill:
        backfill_script = _ROOT / "scripts" / "migration" / "backfill_interruption_fks.py"
        proc = subprocess.run(
            [sys.executable, str(backfill_script), "--execute"],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
            check=False,
        )
        report["backfill_fks"] = {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-4000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
        residuals_script = _ROOT / "scripts" / "migration" / "backfill_interruption_residuals.py"
        proc2 = subprocess.run(
            [sys.executable, str(residuals_script), "--execute"],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
            check=False,
        )
        report["backfill_residuals"] = {
            "exit_code": proc2.returncode,
            "stdout": proc2.stdout[-4000:] if proc2.stdout else "",
            "stderr": proc2.stderr[-2000:] if proc2.stderr else "",
        }
    else:
        report["backfill_fks"] = {"skipped": dry_run or skip_backfill}

    report["after"] = _sql_counts()
    report["finished_at"] = datetime.now().isoformat()

    out_path = settings.reports_dir / f"sync_interruptions_{datetime.now():%Y%m%d_%H%M%S}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync interruptions HFSQL → SQL Server (extract + insert + update)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    parser.add_argument("--execute", action="store_true", help="Exécuter la synchronisation")
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Réutiliser les JSONL déjà présents dans scripts/migration/exports/",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Ne pas lancer les scripts backfill FK après l'ETL",
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Mettre à jour les interruptions déjà importées (plus lent ; défaut : nouvelles lignes seulement)",
    )
    parser.add_argument(
        "--avec-transport",
        action="store_true",
        help="Ré-extraire aussi InterruptionsTransport, Interruptions_OMVG et EnergieND",
    )
    args = parser.parse_args()
    if not args.execute and not args.dry_run:
        args.dry_run = get_settings().migration_dry_run
    dry_run = not args.execute if args.execute else args.dry_run
    try:
        report = run_sync(
            dry_run=dry_run,
            skip_extract=args.skip_extract,
            skip_backfill=args.skip_backfill,
            update_existing=args.update_existing,
            avec_transport=args.avec_transport,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
