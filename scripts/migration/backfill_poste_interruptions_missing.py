#!/usr/bin/env python3
"""Complète poste_interruptions pour les IDPostes récemment mappés (rejets ITD).

Cible les postes absents lors du premier import (skipped_no_poste).

Usage :
    python scripts/migration/backfill_poste_interruptions_missing.py --dry-run
    python scripts/migration/backfill_poste_interruptions_missing.py --execute
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
from scripts.migration.config import get_settings
from scripts.migration.id_maps import IdMapStore
from scripts.migration.import_poste_interruptions_itd import (
    CONTEXT_BACKFILL_SQL,
    _bulk_insert,
    _create_engine,
    _load_interruption_context,
    _load_legacy_interruption_ids,
)
from scripts.migration.itd_sqlserver import connect_itd
from scripts.migration.transforms.fk_resolver import FkResolver
from sqlalchemy import text


def run(*, dry_run: bool, only_new_codes: bool) -> dict[str, Any]:
    id_maps = IdMapStore()
    fk = FkResolver(id_maps)
    poste_map = {int(k): int(v) for k, v in id_maps.load("postes").items() if str(k).isdigit()}

    engine = _create_engine()
    interruption_ctx = _load_interruption_context(engine)
    with engine.connect() as conn:
        if only_new_codes:
            # Postes bootstrap ITD : codes PIxxxx ou créés sans feeder récemment
            new_ids = {
                int(r[0])
                for r in conn.execute(
                    text(
                        """
                        SELECT id FROM dbo.postes
                        WHERE code LIKE 'PI%' OR (feeder_id IS NULL AND id > 33962)
                        """
                    )
                ).all()
            }
            target_legacy = [lid for lid, sid in poste_map.items() if sid in new_ids]
        else:
            target_legacy = list(poste_map.keys())

    legacy_interruptions = set(_load_legacy_interruption_ids(distribution_only=True))
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "target_postes": len(target_legacy),
        "inserted": 0,
        "skipped_no_interruption": 0,
        "skipped_zero_clients": 0,
        "skipped_existing": 0,
    }
    if not target_legacy:
        return report

    # Chunk IDPostes pour requête ITD
    chunk_size = 100
    pending: list[tuple[int, int, int, int | None, int | None, int | None]] = []
    engine_holder = [engine]

    itd = connect_itd()
    try:
        for i in range(0, len(target_legacy), chunk_size):
            batch = target_legacy[i : i + chunk_size]
            placeholders = ",".join("?" for _ in batch)
            cur = itd.cursor()
            cur.execute(
                f"""
                SELECT
                    pi.NInterruption,
                    pi.IDPostes,
                    SUM(COALESCE(pi.nombreclientposteEstime, 0)) AS nombre_clients
                FROM dbo.PosteInterruption pi
                WHERE pi.IDPostes IN ({placeholders})
                GROUP BY pi.NInterruption, pi.IDPostes
                """,
                batch,
            )
            for n_interruption, id_postes, nombre_clients in cur.fetchall():
                if int(n_interruption) not in legacy_interruptions:
                    # encore tenter via map (peut être hors liste filtrée)
                    pass
                interruption_id = fk.interruption_id(n_interruption)
                if interruption_id is None:
                    report["skipped_no_interruption"] += 1
                    continue
                poste_id = poste_map.get(int(id_postes))
                if poste_id is None:
                    continue
                clients = int(nombre_clients or 0)
                if clients <= 0:
                    report["skipped_zero_clients"] += 1
                    continue
                feeder_id, service_id, poste_source_id = interruption_ctx.get(
                    int(interruption_id), (None, None, None)
                )
                pending.append(
                    (
                        int(interruption_id),
                        int(poste_id),
                        clients,
                        feeder_id,
                        service_id,
                        poste_source_id,
                    )
                )
                if len(pending) >= 2000:
                    n = _bulk_insert(
                        engine_holder, pending, dry_run=dry_run, skip_existing=True
                    )
                    report["inserted"] += n
                    pending.clear()
    finally:
        itd.close()

    if pending:
        n = _bulk_insert(engine_holder, pending, dry_run=dry_run, skip_existing=True)
        report["inserted"] += n

    if not dry_run:
        with engine_holder[0].begin() as conn:
            result = conn.execute(text(CONTEXT_BACKFILL_SQL))
            report["context_backfill_rowcount"] = result.rowcount

    with engine_holder[0].connect() as conn:
        report["poste_interruptions_count"] = int(
            conn.execute(text("SELECT COUNT(*) FROM dbo.poste_interruptions")).scalar_one()
        )
    engine_holder[0].dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--all-mapped-postes",
        action="store_true",
        help="Parcourt tous les postes mappés (plus lent)",
    )
    args = parser.parse_args()
    dry_run = args.dry_run or not args.execute
    report = run(dry_run=dry_run, only_new_codes=not args.all_mapped_postes)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    path = get_settings().reports_dir / "backfill_poste_interruptions_missing.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
