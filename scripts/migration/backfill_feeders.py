#!/usr/bin/env python3
"""Rattache les IDFeeder HFSQL numériques aux feeders SIRV2 (export JSONL décalé).

Règle métier : chaque feeder doit avoir un poste_source_id valide (HFSQL IDPosteSource / PosteSource).
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
from app.models.reseau import Feeder, PosteSource
from scripts.migration.config import get_settings
from scripts.migration.db_session import get_session
from scripts.migration.hfsql_odbc import connect_hfsql, iter_fetch
from scripts.migration.hfsql_schema import FEEDER_ETL_COLUMNS, POSTE_SOURCE_ETL_COLUMNS
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, select, text

from scripts.migration.backfill_interruption_fks import _sync_url


def _iter_feeders_live() -> list[dict[str, Any]]:
    cols_sql = ",".join(FEEDER_ETL_COLUMNS)
    conn = connect_hfsql()
    try:
        return list(iter_fetch(conn, f"SELECT {cols_sql} FROM Feeders"))
    finally:
        conn.close()


def _iter_postes_sources_live() -> list[dict[str, Any]]:
    cols_sql = ",".join(POSTE_SOURCE_ETL_COLUMNS)
    conn = connect_hfsql()
    try:
        return list(iter_fetch(conn, f"SELECT {cols_sql} FROM PostesSources"))
    finally:
        conn.close()


def _find_poste_source_id(session, id_maps: IdMapStore, libelle: str) -> int | None:
    key = text_key(libelle)
    if not key:
        return None
    mapped = id_maps.lookup_text("postes_sources_by_text", key)
    if mapped is not None:
        return int(mapped)
    existing = session.execute(
        select(PosteSource.id).where(PosteSource.libelle == libelle[:200])
    ).scalar_one_or_none()
    return int(existing) if existing is not None else None


def sync_poste_source_legacy_maps(
    session, id_maps: IdMapStore, *, dry_run: bool
) -> dict[str, int]:
    """Remplit postes_sources.json (ID legacy HFSQL → id SIR) par libellé."""
    stats = {"hfsql_rows": 0, "mapped": 0, "created": 0, "unmatched": 0}
    for row in _iter_postes_sources_live():
        stats["hfsql_rows"] += 1
        legacy_id = row_get(row, "IDPosteSource", "idpostesource")
        libelle = str(row_get(row, "PosteSource", "postesource") or "").strip()
        if not libelle:
            stats["unmatched"] += 1
            continue
        if id_maps.get("postes_sources", legacy_id):
            stats["mapped"] += 1
            continue
        sir_id = _find_poste_source_id(session, id_maps, libelle)
        if sir_id is None and not dry_run:
            code = slug_code(libelle)
            if session.execute(
                select(PosteSource.id).where(PosteSource.code == code)
            ).scalar_one_or_none():
                code = slug_code(f"{libelle}_{legacy_id}", max_len=20)
            obj = PosteSource(code=code, libelle=libelle[:200], is_active=True)
            session.add(obj)
            session.flush()
            sir_id = int(obj.id)
            stats["created"] += 1
        elif sir_id is not None:
            stats["mapped"] += 1
        else:
            stats["unmatched"] += 1
            continue
        if sir_id is not None and sir_id > 0:
            id_maps.put("postes_sources", legacy_id, sir_id)
            key = text_key(libelle)
            if key:
                id_maps.put("postes_sources_by_text", key, sir_id)

    if not dry_run:
        id_maps.save("postes_sources")
        id_maps.save("postes_sources_by_text")
    return stats


def _resolve_poste_source_id(
    session,
    fk: FkResolver,
    id_maps: IdMapStore,
    row: dict[str, Any],
    cache: dict[str, int],
    *,
    dry_run: bool,
) -> int | None:
    ps_legacy = row_get(row, "IDPosteSource", "idpostesource")
    if ps_legacy is not None:
        try:
            if int(ps_legacy) > 0:
                ps_id = id_maps.get("postes_sources", ps_legacy)
                if ps_id is not None:
                    return int(ps_id)
        except (TypeError, ValueError):
            pass
    ps_text = str(row_get(row, "PosteSource", "postesource") or "").strip()
    if ps_text:
        cache_key = text_key(ps_text) or ps_text
        if cache_key in cache:
            return cache[cache_key]
        ps_id = fk.poste_source_id(ps_text)
        if ps_id is None:
            ps_id = _find_poste_source_id(session, id_maps, ps_text)
        if ps_id is None and not dry_run:
            code = slug_code(ps_text)
            if session.execute(
                select(PosteSource.id).where(PosteSource.code == code)
            ).scalar_one_or_none():
                code = slug_code(f"{ps_text}_{ps_legacy or 0}", max_len=20)
            obj = PosteSource(code=code, libelle=ps_text[:200], is_active=True)
            session.add(obj)
            session.flush()
            ps_id = int(obj.id)
            key = text_key(ps_text)
            if key:
                id_maps.put("postes_sources_by_text", key, ps_id)
        if ps_id is not None:
            cache[cache_key] = int(ps_id)
            return int(ps_id)
    return None


def sync_feeder_poste_source_ids(
    engine, id_maps: IdMapStore, fk: FkResolver, *, dry_run: bool
) -> dict[str, int]:
    """Met à jour feeders.poste_source_id depuis HFSQL (par IDFeeder legacy)."""
    updates: dict[int, int] = {}
    for row in _iter_feeders_live():
        sir_feeder_id = id_maps.get("feeders", row_get(row, "IDFeeder", "idfeeder"))
        if sir_feeder_id is None:
            continue
        ps_legacy = row_get(row, "IDPosteSource", "idpostesource")
        ps_text = str(row_get(row, "PosteSource", "postesource") or "").strip()
        ps_id = None
        if ps_legacy is not None:
            try:
                if int(ps_legacy) > 0:
                    ps_id = id_maps.get("postes_sources", ps_legacy)
            except (TypeError, ValueError):
                pass
        if ps_id is None and ps_text:
            ps_id = fk.poste_source_id(ps_text)
        if ps_id is not None:
            updates[int(sir_feeder_id)] = int(ps_id)

    applied = 0
    if updates and not dry_run:
        items = list(updates.items())
        for i in range(0, len(items), 500):
            chunk = items[i : i + 500]
            values_sql = ",".join(f"({fid},{psid})" for fid, psid in chunk)
            sql = (
                "UPDATE f SET poste_source_id = v.psid "
                "FROM dbo.feeders f "
                f"INNER JOIN (VALUES {values_sql}) AS v(id, psid) ON f.id = v.id "
                "WHERE f.poste_source_id IS NULL OR f.poste_source_id <> v.psid"
            )
            with engine.begin() as conn:
                conn.execute(text(sql))
            applied += len(chunk)

    return {"feeders_to_update": len(updates), "feeders_updated": applied}


def _find_feeder_id(
    session,
    id_maps: IdMapStore,
    libelle: str,
    by_libelle: dict[str, int],
) -> int | None:
    key = text_key(libelle)
    if not key:
        return None
    if key in by_libelle:
        return by_libelle[key]
    mapped = id_maps.lookup_text("feeders_by_text", key)
    if mapped is not None:
        by_libelle[key] = int(mapped)
        return int(mapped)
    existing = session.execute(
        select(Feeder.id).where(Feeder.libelle == libelle[:200])
    ).scalar_one_or_none()
    if existing is not None:
        by_libelle[key] = int(existing)
        return int(existing)
    return None


def backfill_feeders(*, dry_run: bool) -> dict[str, Any]:
    settings = get_settings()
    id_maps = IdMapStore(settings.id_maps_dir)
    fk = FkResolver(id_maps)
    rows = _iter_feeders_live()
    engine = create_engine(_sync_url(), pool_pre_ping=True)

    report: dict[str, Any] = {}
    stats: dict[str, int] = {
        "hfsql_rows": len(rows),
        "numeric_legacy_mapped": 0,
        "inserted": 0,
        "linked_existing": 0,
        "skipped_no_libelle": 0,
        "skipped_no_idfeeder": 0,
        "skipped_no_poste_source": 0,
    }

    by_libelle: dict[str, int] = {}
    ps_cache: dict[str, int] = {}

    try:
        with get_session() as session:
            report["poste_source_maps"] = sync_poste_source_legacy_maps(
                session, id_maps, dry_run=dry_run
            )
            fk = FkResolver(id_maps)

            for row in session.execute(select(Feeder.id, Feeder.libelle)):
                key = text_key(row.libelle)
                if key:
                    by_libelle[key] = int(row.id)

            for row in rows:
                libelle = str(row_get(row, "Feeder", "feeder") or "").strip()
                raw_id = row_get(row, "IDFeeder", "idfeeder")
                try:
                    legacy_num = int(raw_id)
                except (TypeError, ValueError):
                    stats["skipped_no_idfeeder"] += 1
                    continue
                if legacy_num <= 0:
                    stats["skipped_no_idfeeder"] += 1
                    continue
                if not libelle:
                    stats["skipped_no_libelle"] += 1
                    continue

                legacy_key = str(legacy_num)
                existing_mapped = id_maps.get("feeders", legacy_key)
                if existing_mapped is not None:
                    stats["numeric_legacy_mapped"] += 1
                    key = text_key(libelle)
                    if key:
                        id_maps.put("feeders_by_text", key, int(existing_mapped))
                    continue

                sir_id = _find_feeder_id(session, id_maps, libelle, by_libelle)
                if sir_id is None and not dry_run:
                    ps_id = _resolve_poste_source_id(
                        session, fk, id_maps, row, ps_cache, dry_run=dry_run
                    )
                    if ps_id is None:
                        stats["skipped_no_poste_source"] += 1
                        continue
                    service_id = fk.resolve_service_id(
                        {"Service": row_get(row, "Service", "service")}
                    )
                    code = slug_code(libelle)
                    if session.execute(
                        select(Feeder.id).where(Feeder.code == code)
                    ).scalar_one_or_none():
                        code = slug_code(f"{libelle}_{legacy_key}", max_len=20)
                    obj = Feeder(
                        poste_source_id=ps_id,
                        service_id=service_id,
                        code=code,
                        libelle=libelle[:200],
                        tension_kv=row_get(row, "TensionPrimaire", "tensionprimaire"),
                        is_active=True,
                    )
                    session.add(obj)
                    session.flush()
                    sir_id = int(obj.id)
                    stats["inserted"] += 1
                elif sir_id is not None:
                    stats["linked_existing"] += 1
                elif dry_run:
                    stats["inserted"] += 1
                    sir_id = -1
                else:
                    continue

                if sir_id is not None and sir_id > 0:
                    id_maps.put("feeders", legacy_key, sir_id)
                    stats["numeric_legacy_mapped"] += 1
                    key = text_key(libelle)
                    if key:
                        id_maps.put("feeders_by_text", key, sir_id)
                        by_libelle[key] = sir_id
                    text_legacy = f"T:{key}" if key else None
                    if text_legacy:
                        id_maps.put("feeders", text_legacy, sir_id)

            if dry_run:
                session.rollback()
            else:
                session.commit()

        id_maps.save("feeders")
        id_maps.save("feeders_by_text")

        report["feeders"] = stats
        report["feeder_poste_sources"] = sync_feeder_poste_source_ids(
            engine, id_maps, fk, dry_run=dry_run
        )
    finally:
        engine.dispose()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill mappings IDFeeder → feeders SIRV2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.execute:
        parser.error("Spécifiez --dry-run ou --execute")

    report = backfill_feeders(dry_run=args.dry_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
