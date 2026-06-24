#!/usr/bin/env python3
"""Rétro-lien FK interruptions depuis HFSQL (ID legacy + texte)."""

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
from scripts.migration.hfsql_odbc import connect_hfsql, iter_fetch, load_table_rows
from scripts.migration.hfsql_schema import fk_columns_for_table
from scripts.migration.id_map_text_loader import rebuild_text_maps
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

INTERRUPTION_TABLES: list[tuple[str, str]] = [
    ("Interruptions_Histo", "distribution"),
    ("InterruptionsTransport", "transport"),
    ("Interruptions_OMVG", "transport"),
    ("Interruptions", "distribution"),
]

FK_FIELDS = (
    "service_id",
    "feeder_id",
    "cause_id",
    "nature_id",
    "siege_id",
    "signalisation_id",
)

_FK_TABLE_BY_FIELD: dict[str, str] = {
    "service_id": "services",
    "feeder_id": "feeders",
    "cause_id": "causes",
    "nature_id": "natures",
    "siege_id": "sieges",
    "signalisation_id": "signalisations",
}


def _sync_url() -> str:
    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def _load_valid_fk_ids(engine) -> dict[str, set[int]]:
    """IDs réellement présents en base — évite les violations FK (id_maps obsolètes)."""
    valid: dict[str, set[int]] = {}
    for field, table in _FK_TABLE_BY_FIELD.items():
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT id FROM dbo.{table}")).all()
        valid[field] = {int(r[0]) for r in rows}
    return valid


def _filter_updates_by_valid_fks(
    updates: dict[int, dict[str, int]],
    valid_ids: dict[str, set[int]],
) -> tuple[dict[int, dict[str, int]], dict[str, int]]:
    """Retire les valeurs FK absentes de la cible SQL Server."""
    filtered: dict[int, dict[str, int]] = {}
    rejected: dict[str, int] = {field: 0 for field in FK_FIELDS}
    for sir_id, vals in updates.items():
        kept: dict[str, int] = {}
        for field, value in vals.items():
            if field in valid_ids and int(value) in valid_ids[field]:
                kept[field] = int(value)
            elif field in valid_ids:
                rejected[field] += 1
            else:
                kept[field] = int(value)
        if kept:
            filtered[sir_id] = kept
    return filtered, rejected


def _load_feeder_service_map(engine) -> dict[int, int | None]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, service_id FROM dbo.feeders WHERE service_id IS NOT NULL")
        ).all()
    return {int(r[0]): int(r[1]) if r[1] is not None else None for r in rows}


def _build_region_agence_map(engine) -> dict[int, int]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT d.region_id, MIN(a.id) AS agence_id
                FROM dbo.agences a
                INNER JOIN dbo.delegations d ON d.id = a.delegation_id
                GROUP BY d.region_id
                """
            )
        ).all()
    return {int(r[0]): int(r[1]) for r in rows}


def backfill_service_agences(engine, id_maps: IdMapStore, *, dry_run: bool) -> dict[str, int]:
    """Recalcule services.agence_id depuis HFSQL Services.Region."""
    region_agence = _build_region_agence_map(engine)
    updates: dict[int, int] = {}
    for row in load_table_rows("Services"):
        legacy_id = row_get(row, "IDAUTO", "idauto")
        sir_id = id_maps.get("services", legacy_id)
        if sir_id is None:
            continue
        region_text = str(row_get(row, "Region", "region") or "").strip()
        if not region_text:
            continue
        region_id = id_maps.lookup_text("regions_by_text", text_key(region_text))
        if region_id is None:
            continue
        agence_id = region_agence.get(int(region_id))
        if agence_id is not None:
            updates[int(sir_id)] = agence_id

    if not dry_run and updates:
        items = list(updates.items())
        for i in range(0, len(items), 500):
            chunk = items[i : i + 500]
            values_sql = ",".join(f"({sid},{aid})" for sid, aid in chunk)
            sql = (
                "UPDATE s SET agence_id = v.agence_id "
                "FROM dbo.services s "
                f"INNER JOIN (VALUES {values_sql}) AS v(id, agence_id) ON s.id = v.id "
                "WHERE s.agence_id IS NULL OR s.agence_id <> v.agence_id"
            )
            with engine.begin() as conn:
                conn.execute(text(sql))

    return {"service_agences_to_update": len(updates)}


def _iter_fk_rows(table: str, legacy_ids: list[str], *, chunk_size: int = 200):
    """Requêtes HFSQL ciblées avec colonnes FK minimales (évite décalage ODBC)."""
    if not legacy_ids:
        return
    cols_sql = ",".join(fk_columns_for_table(table))
    conn = connect_hfsql()
    try:
        for i in range(0, len(legacy_ids), chunk_size):
            chunk = legacy_ids[i : i + chunk_size]
            ids_sql = ",".join(str(int(x)) for x in chunk)
            query = f"SELECT {cols_sql} FROM {table} WHERE NInterruption IN ({ids_sql})"
            yield from iter_fetch(conn, query)
    finally:
        conn.close()


def collect_interruption_updates(
    id_maps: IdMapStore,
    feeder_services: dict[int, int | None],
) -> dict[int, dict[str, int]]:
    fk = FkResolver(id_maps)
    inter_map = id_maps.load("interruptions")
    legacy_ids = list(inter_map.keys())
    updates: dict[int, dict[str, int]] = {}
    stats: dict[str, int] = {
        "rows_seen": 0,
        "mapped": 0,
        "unmapped_legacy": 0,
    }

    for table, type_reseau in INTERRUPTION_TABLES:
        for row in _iter_fk_rows(table, legacy_ids):
            stats["rows_seen"] += 1
            legacy_id = row_get(row, "NInterruption", "ninterruption")
            sir_id = inter_map.get(str(legacy_id))
            if sir_id is None:
                stats["unmapped_legacy"] += 1
                continue
            stats["mapped"] += 1
            sir_id = int(sir_id)

            service_id = fk.resolve_service_id(row)
            feeder_id = fk.resolve_feeder_id(row)
            if service_id is None and feeder_id is not None:
                service_id = feeder_services.get(feeder_id)

            payload: dict[str, int] = {}
            if service_id is not None:
                payload["service_id"] = int(service_id)
            if feeder_id is not None:
                payload["feeder_id"] = int(feeder_id)

            cause_id = fk.resolve_cause_id(row, type_reseau)
            if cause_id is not None:
                payload["cause_id"] = int(cause_id)
            nature_id = fk.resolve_nature_id(row)
            if nature_id is not None:
                payload["nature_id"] = int(nature_id)
            siege_id = fk.resolve_siege_id(row, type_reseau)
            if siege_id is not None:
                payload["siege_id"] = int(siege_id)
            signalisation_id = fk.resolve_signalisation_id(row, type_reseau)
            if signalisation_id is not None:
                payload["signalisation_id"] = int(signalisation_id)

            if payload:
                existing = updates.get(sir_id, {})
                existing.update(payload)
                updates[sir_id] = existing

    stats["interruptions_with_updates"] = len(updates)
    return updates, stats


def apply_interruption_updates(
    engine, updates: dict[int, dict[str, int]], batch_size: int = 1000
) -> dict[str, int]:
    applied = {field: 0 for field in FK_FIELDS}
    items = list(updates.items())
    for field in FK_FIELDS:
        field_updates = [(sid, vals[field]) for sid, vals in items if field in vals]
        for i in range(0, len(field_updates), batch_size):
            chunk = field_updates[i : i + batch_size]
            values_sql = ",".join(f"({sid},{val})" for sid, val in chunk)
            sql = (
                f"UPDATE i SET {field} = v.val "
                f"FROM dbo.interruptions i "
                f"INNER JOIN (VALUES {values_sql}) AS v(id, val) ON i.id = v.id "
                f"WHERE i.{field} IS NULL OR i.{field} <> v.val"
            )
            with engine.begin() as conn:
                conn.execute(text(sql))
            applied[field] += len(chunk)
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill FK interruptions depuis HFSQL")
    parser.add_argument("--dry-run", action="store_true", help="Statistiques sans écriture")
    parser.add_argument("--execute", action="store_true", help="Appliquer les mises à jour")
    parser.add_argument(
        "--geo-services",
        action="store_true",
        help="Recalculer services.agence_id depuis HFSQL Services.Region",
    )
    args = parser.parse_args()
    if not args.dry_run and not args.execute:
        parser.error("Spécifiez --dry-run ou --execute")

    settings = get_settings()
    id_maps = IdMapStore(settings.id_maps_dir)
    text_counts = rebuild_text_maps(id_maps)
    report: dict[str, Any] = {"text_maps_rebuilt": text_counts}

    engine = create_engine(_sync_url(), pool_pre_ping=True)

    try:
        if args.geo_services or args.execute:
            report["geo_services"] = backfill_service_agences(
                engine, id_maps, dry_run=args.dry_run
            )

        feeder_services = _load_feeder_service_map(engine)
        updates, stats = collect_interruption_updates(id_maps, feeder_services)
        report["collect"] = stats
        valid_ids = _load_valid_fk_ids(engine)
        updates, rejected = _filter_updates_by_valid_fks(updates, valid_ids)
        if any(rejected.values()):
            report["fk_rejected_invalid_id"] = rejected
        report["fields_populated"] = {
            field: sum(1 for vals in updates.values() if field in vals) for field in FK_FIELDS
        }

        if args.execute and updates:
            report["applied"] = apply_interruption_updates(engine, updates)
    finally:
        engine.dispose()

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
