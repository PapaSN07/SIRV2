#!/usr/bin/env python3
"""Corrige les résidus FK interruptions (service, cause, dérivation feeder).

Interruption #189 (HFSQL 66277) volontairement ignorée — voir validate_migration.IGNORED_INTERRUPTION_IDS.
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
from scripts.migration.backfill_interruption_fks import (
    _filter_updates_by_valid_fks,
    _iter_fk_rows,
    _load_valid_fk_ids,
    _sync_url,
    apply_interruption_updates,
)
from scripts.migration.config import get_settings
from scripts.migration.hfsql_odbc import connect_hfsql, iter_fetch
from scripts.migration.hfsql_schema import FEEDER_ETL_COLUMNS
from scripts.migration.id_map_text_loader import rebuild_text_maps
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

DEFAULT_CAUSE_LIBELLE = "Inconnue"


def _cause_inconnue_id(engine) -> int | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM dbo.causes WHERE libelle = :lib"),
            {"lib": DEFAULT_CAUSE_LIBELLE},
        ).scalar_one_or_none()
    return int(row) if row is not None else None


def backfill_feeder_service_ids(engine, id_maps: IdMapStore, *, dry_run: bool) -> dict[str, int]:
    """Renseigne feeders.service_id depuis HFSQL Feeders.Service."""
    fk = FkResolver(id_maps)
    cols_sql = ",".join(FEEDER_ETL_COLUMNS)
    conn = connect_hfsql()
    try:
        rows = list(iter_fetch(conn, f"SELECT {cols_sql} FROM Feeders"))
    finally:
        conn.close()

    updates: dict[int, int] = {}
    for row in rows:
        legacy_id = row_get(row, "IDFeeder", "idfeeder")
        sir_feeder_id = id_maps.get("feeders", legacy_id)
        if sir_feeder_id is None:
            continue
        service_id = fk.resolve_service_id({"Service": row_get(row, "Service", "service")})
        if service_id is not None:
            updates[int(sir_feeder_id)] = int(service_id)

    applied = 0
    if updates and not dry_run:
        items = list(updates.items())
        for i in range(0, len(items), 500):
            chunk = items[i : i + 500]
            values_sql = ",".join(f"({fid},{sid})" for fid, sid in chunk)
            sql = (
                "UPDATE f SET service_id = v.sid "
                "FROM dbo.feeders f "
                f"INNER JOIN (VALUES {values_sql}) AS v(id, sid) ON f.id = v.id "
                "WHERE f.service_id IS NULL OR f.service_id <> v.sid"
            )
            with engine.begin() as conn:
                conn.execute(text(sql))
            applied += len(chunk)

    return {"feeders_to_update": len(updates), "feeders_updated": applied if not dry_run else 0}


def derive_service_from_feeder(engine, *, dry_run: bool) -> dict[str, int]:
    sql = """
        UPDATE i SET service_id = f.service_id
        FROM dbo.interruptions i
        INNER JOIN dbo.feeders f ON f.id = i.feeder_id
        WHERE i.type_direction = 'distribution'
          AND i.service_id IS NULL
          AND f.service_id IS NOT NULL
    """
    if dry_run:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM dbo.interruptions i
                    INNER JOIN dbo.feeders f ON f.id = i.feeder_id
                    WHERE i.type_direction = 'distribution'
                      AND i.service_id IS NULL
                      AND f.service_id IS NOT NULL
                    """
                )
            ).scalar()
        return {"interruptions_to_update": int(count or 0), "interruptions_updated": 0}

    with engine.begin() as conn:
        result = conn.execute(text(sql))
        updated = int(result.rowcount or 0)
    return {"interruptions_to_update": updated, "interruptions_updated": updated}


def apply_default_cause(engine, cause_id: int, *, dry_run: bool) -> dict[str, int]:
    if dry_run:
        with engine.connect() as conn:
            count = conn.execute(
                text(
                    """
                    SELECT COUNT(*) FROM dbo.interruptions
                    WHERE type_direction = 'distribution' AND cause_id IS NULL
                    """
                )
            ).scalar()
        return {"interruptions_to_update": int(count or 0), "interruptions_updated": 0}

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE dbo.interruptions
                SET cause_id = :cause_id
                WHERE type_direction = 'distribution' AND cause_id IS NULL
                """
            ),
            {"cause_id": cause_id},
        )
        updated = int(result.rowcount or 0)
    return {"interruptions_to_update": updated, "interruptions_updated": updated}


def backfill_remaining_service_from_hfsql(
    engine, id_maps: IdMapStore, *, dry_run: bool
) -> dict[str, Any]:
    """Tente service_id via HFSQL (idservice / Service) sur les NULL restants."""
    fk = FkResolver(id_maps)
    inter = id_maps.load("interruptions")
    legacy_to_sir = {k: int(v) for k, v in inter.items()}

    with engine.connect() as conn:
        null_ids = [
            int(r[0])
            for r in conn.execute(
                text(
                    """
                    SELECT id FROM dbo.interruptions
                    WHERE type_direction = 'distribution' AND service_id IS NULL
                    """
                )
            ).all()
        ]

    null_set = set(null_ids)
    legacy_ids = [leg for leg, sid in legacy_to_sir.items() if sid in null_set]
    updates: dict[int, int] = {}

    for table in ("Interruptions_Histo", "Interruptions"):
        for row in _iter_fk_rows(table, legacy_ids, chunk_size=200):
            legacy = str(row_get(row, "NInterruption", "ninterruption"))
            sir_id = legacy_to_sir.get(legacy)
            if sir_id is None or sir_id not in null_set:
                continue
            service_id = fk.resolve_service_id(row)
            if service_id is not None:
                updates[sir_id] = int(service_id)

    valid = _load_valid_fk_ids(engine)
    filtered, rejected = _filter_updates_by_valid_fks(
        {sid: {"service_id": val} for sid, val in updates.items()},
        valid,
    )
    applied = 0
    if filtered and not dry_run:
        applied = apply_interruption_updates(engine, filtered)["service_id"]

    return {
        "candidates": len(updates),
        "rejected_invalid": rejected.get("service_id", 0),
        "interruptions_updated": applied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill résidus FK interruptions")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.execute:
        parser.error("Spécifiez --dry-run ou --execute")

    settings = get_settings()
    id_maps = IdMapStore(settings.id_maps_dir)
    rebuild_text_maps(id_maps)
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    report: dict[str, Any] = {}

    try:
        cause_id = _cause_inconnue_id(engine)
        if cause_id is None:
            raise RuntimeError(f"Cause '{DEFAULT_CAUSE_LIBELLE}' introuvable en base")

        report["feeder_services"] = backfill_feeder_service_ids(
            engine, id_maps, dry_run=args.dry_run
        )
        report["derive_service_from_feeder"] = derive_service_from_feeder(
            engine, dry_run=args.dry_run
        )
        report["hfsql_service"] = backfill_remaining_service_from_hfsql(
            engine, id_maps, dry_run=args.dry_run
        )
        report["default_cause"] = apply_default_cause(
            engine, cause_id, dry_run=args.dry_run
        )

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                      SUM(CASE WHEN service_id IS NULL THEN 1 ELSE 0 END) AS sans_service,
                      SUM(CASE WHEN feeder_id IS NULL THEN 1 ELSE 0 END) AS sans_feeder,
                      SUM(CASE WHEN cause_id IS NULL THEN 1 ELSE 0 END) AS sans_cause
                    FROM dbo.interruptions WHERE type_direction = 'distribution'
                    """
                )
            ).mappings().first()
        report["remaining_nulls"] = dict(row) if row else {}
    finally:
        engine.dispose()

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
