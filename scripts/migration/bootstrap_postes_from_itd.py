#!/usr/bin/env python3
"""Crée les postes SIRV2 manquants référencés par ITD PosteInterruption.

Les IDPostes présents dans IndicateursTransportDistribution mais absents de
dbo.postes / id_maps causent skipped_no_poste à l'import.

Usage :
    python scripts/migration/bootstrap_postes_from_itd.py --dry-run
    python scripts/migration/bootstrap_postes_from_itd.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.id_maps import IdMapStore
from scripts.migration.itd_sqlserver import connect_itd
from scripts.migration.transforms.codes import slug_code, text_key
from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings


def _url() -> str:
    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def run(*, dry_run: bool) -> dict[str, Any]:
    ensure_dirs()
    id_maps = IdMapStore()
    id_maps.load("postes")
    id_maps.load("postes_by_text")
    known = {int(k) for k in id_maps.load("postes") if str(k).isdigit()}

    itd = connect_itd()
    try:
        cur = itd.cursor()
        cur.execute(
            """
            SELECT IDPostes, MAX(Posteconcerne) AS libelle
            FROM dbo.PosteInterruption
            WHERE IDPostes IS NOT NULL AND IDPostes > 0
            GROUP BY IDPostes
            """
        )
        rows = [(int(r[0]), (r[1] or f"POSTE_{r[0]}").strip()) for r in cur.fetchall()]
    finally:
        itd.close()

    missing = [(lid, lib) for lid, lib in rows if lid not in known]
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "itd_distinct_postes": len(rows),
        "already_mapped": len(rows) - len(missing),
        "missing": len(missing),
        "inserted": 0,
    }
    if dry_run or not missing:
        report["sample_missing"] = missing[:10]
        return report

    engine = create_engine(_url(), pool_pre_ping=True)
    with engine.begin() as conn:
        for lid, libelle in missing:
            code = slug_code(str(lid), prefix="P")[:20]
            # éviter collision de code
            exists = conn.execute(
                text("SELECT id FROM dbo.postes WHERE code = :c"), {"c": code}
            ).scalar_one_or_none()
            if exists is not None:
                code = f"PI{lid}"[:20]
            result = conn.execute(
                text(
                    """
                    INSERT INTO dbo.postes (code, libelle, feeder_id, service_id, is_active)
                    OUTPUT INSERTED.id
                    VALUES (:code, :libelle, NULL, NULL, 1)
                    """
                ),
                {"code": code, "libelle": str(libelle)[:200]},
            )
            new_id = int(result.scalar_one())
            id_maps.put("postes", lid, new_id)
            key = text_key(libelle)
            if key:
                id_maps.put("postes_by_text", key, new_id)
            report["inserted"] += 1

    id_maps.save("postes")
    id_maps.save("postes_by_text")
    engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = args.dry_run or not args.execute
    report = run(dry_run=dry_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    path = get_settings().reports_dir / "bootstrap_postes_from_itd.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
