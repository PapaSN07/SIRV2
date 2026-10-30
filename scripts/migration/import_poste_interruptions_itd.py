#!/usr/bin/env python3
"""Import dbo.poste_interruptions depuis IndicateursTransportDistribution.PosteInterruption.

Source : srv-bddomtech / IndicateursTransportDistribution (table PosteInterruption).
Cible  : SIRV2 / dbo.poste_interruptions (clients touchés pour SAIFI/SAIDI).

Usage :
    python scripts/migration/import_poste_interruptions_itd.py --dry-run
    python scripts/migration/import_poste_interruptions_itd.py --execute
    python scripts/migration/import_poste_interruptions_itd.py --execute --truncate
    python scripts/migration/import_poste_interruptions_itd.py --execute --limit-chunks 5
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.id_maps import IdMapStore
from scripts.migration.itd_sqlserver import connect_itd
from scripts.migration.transforms.fk_resolver import FkResolver
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

AGG_QUERY = """
SELECT
    pi.NInterruption,
    pi.IDPostes,
    MAX(pi.Posteconcerne) AS Posteconcerne,
    SUM(COALESCE(pi.nombreclientposteEstime, 0)) AS nombre_clients
FROM dbo.PosteInterruption pi
WHERE pi.NInterruption IN ({placeholders})
GROUP BY pi.NInterruption, pi.IDPostes
"""


def _sync_url() -> str:
    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def _load_legacy_interruption_ids(*, distribution_only: bool, depuis: datetime | None = None) -> list[int]:
    """Legacy ids migrés ; ``depuis`` : seulement les interruptions apparues à partir de cette date (delta)."""
    id_maps = IdMapStore()
    interruption_map: dict[str, int] = {
        str(k): int(v) for k, v in id_maps.load("interruptions").items()
    }
    if not distribution_only and depuis is None:
        return sorted(int(k) for k in interruption_map if str(k).isdigit())

    sql = "SELECT id FROM dbo.interruptions WHERE 1 = 1"
    if distribution_only:
        sql += " AND type_direction = 'distribution'"
    if depuis is not None:
        sql += " AND date_apparition >= :depuis"
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"depuis": depuis} if depuis is not None else {}).all()
    dist_ids = {int(r[0]) for r in rows}
    engine.dispose()

    legacy_ids: list[int] = []
    for legacy, sir_id in interruption_map.items():
        if not str(legacy).isdigit():
            continue
        if int(sir_id) in dist_ids:
            legacy_ids.append(int(legacy))
    return sorted(legacy_ids)


def _itd_legacy_ids_with_data(itd_conn, legacy_set: set[int]) -> list[int]:
    """Intersection des NInterruption ITD avec les legacy ids migrés."""
    cur = itd_conn.cursor()
    cur.execute("SELECT DISTINCT NInterruption FROM dbo.PosteInterruption")
    return sorted(int(row[0]) for row in cur.fetchall() if int(row[0]) in legacy_set)


def _fetch_aggregated_batch(itd_conn, legacy_batch: list[int]) -> list[tuple[Any, ...]]:
    placeholders = ",".join("?" for _ in legacy_batch)
    query = AGG_QUERY.format(placeholders=placeholders)
    cur = itd_conn.cursor()
    cur.execute(query, legacy_batch)
    return list(cur.fetchall())


def _create_engine():
    return create_engine(
        _sync_url(),
        pool_pre_ping=True,
        pool_recycle=180,
        connect_args={"timeout": 90},
    )


def _load_interruption_context(engine) -> dict[int, tuple[int | None, int | None, int | None]]:
    """Map interruption_id → (feeder_id, service_id, poste_source_id)."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, feeder_id, service_id, poste_source_id
                FROM dbo.interruptions
                """
            )
        ).all()
    return {
        int(r[0]): (
            int(r[1]) if r[1] is not None else None,
            int(r[2]) if r[2] is not None else None,
            int(r[3]) if r[3] is not None else None,
        )
        for r in rows
    }


def _bulk_insert(
    engine_holder: list,
    rows: list[tuple[int, int, int, int | None, int | None, int | None]],
    *,
    dry_run: bool,
    skip_existing: bool,
    max_retries: int = 5,
) -> int:
    if not rows or dry_run:
        return len(rows)

    if skip_existing:
        insert_sql = text(
            """
            INSERT INTO dbo.poste_interruptions (
                interruption_id, poste_id, nombre_clients_touches,
                feeder_id, service_id, poste_source_id, date_interruption
            )
            SELECT
                :interruption_id, :poste_id, :nombre_clients_touches,
                :feeder_id, :service_id, :poste_source_id,
                (SELECT i.date_apparition FROM dbo.interruptions i WHERE i.id = :interruption_id)
            WHERE NOT EXISTS (
                SELECT 1 FROM dbo.poste_interruptions pi
                WHERE pi.interruption_id = :interruption_id
                  AND pi.poste_id = :poste_id
            )
            """
        )
    else:
        insert_sql = text(
            """
            INSERT INTO dbo.poste_interruptions (
                interruption_id, poste_id, nombre_clients_touches,
                feeder_id, service_id, poste_source_id, date_interruption
            )
            VALUES (
                :interruption_id, :poste_id, :nombre_clients_touches,
                :feeder_id, :service_id, :poste_source_id,
                (SELECT i.date_apparition FROM dbo.interruptions i WHERE i.id = :interruption_id)
            )
            """
        )

    payload = [
        {
            "interruption_id": interruption_id,
            "poste_id": poste_id,
            "nombre_clients_touches": clients,
            "feeder_id": feeder_id,
            "service_id": service_id,
            "poste_source_id": poste_source_id,
        }
        for interruption_id, poste_id, clients, feeder_id, service_id, poste_source_id in rows
    ]

    for attempt in range(1, max_retries + 1):
        engine = engine_holder[0]
        try:
            with engine.begin() as conn:
                conn.execute(insert_sql, payload)
            return len(rows)
        except OperationalError:
            if attempt >= max_retries:
                raise
            wait = min(30, 2**attempt)
            print(
                f"  retry insert {attempt}/{max_retries}, attente {wait}s…",
                flush=True,
            )
            time.sleep(wait)
            try:
                engine.dispose()
            except Exception:
                pass
            engine_holder[0] = _create_engine()
    return 0


CONTEXT_BACKFILL_SQL = """
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


def run_import(
    *,
    dry_run: bool,
    truncate: bool,
    resume: bool,
    start_chunk: int,
    distribution_only: bool,
    interruption_chunk_size: int,
    insert_batch_size: int,
    limit_chunks: int | None,
    depuis: datetime | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    settings = get_settings()
    started = time.perf_counter()

    id_maps = IdMapStore()
    fk = FkResolver(id_maps)

    legacy_ids = _load_legacy_interruption_ids(distribution_only=distribution_only, depuis=depuis)
    legacy_set = set(legacy_ids)
    itd_conn = connect_itd()
    try:
        itd_legacy_ids = _itd_legacy_ids_with_data(itd_conn, legacy_set)
    finally:
        itd_conn.close()

    stats: dict[str, Any] = {
        "dry_run": dry_run,
        "distribution_only": distribution_only,
        "legacy_interruptions_mapped": len(legacy_ids),
        "legacy_interruptions_in_itd": len(itd_legacy_ids),
        "source_database": settings.itd_database,
        "inserted": 0,
        "skipped_no_interruption": 0,
        "skipped_no_poste": 0,
        "skipped_zero_clients": 0,
        "chunks_processed": 0,
        "start_chunk": start_chunk,
        "resume": resume,
        "errors": 0,
    }

    engine = _create_engine()
    engine_holder = [engine]
    interruption_ctx = _load_interruption_context(engine)
    skip_existing = resume or start_chunk > 0
    if truncate and not dry_run and not resume:
        with engine.begin() as conn:
            before = conn.execute(text("SELECT COUNT(*) FROM dbo.poste_interruptions")).scalar_one()
            conn.execute(text("TRUNCATE TABLE dbo.poste_interruptions"))
        stats["truncated_before"] = int(before)

    pending_insert: list[tuple[int, int, int, int | None, int | None, int | None]] = []
    chunks_total = (
        (len(itd_legacy_ids) + interruption_chunk_size - 1) // interruption_chunk_size
        if itd_legacy_ids
        else 0
    )
    chunks_to_run = chunks_total if limit_chunks is None else min(
        start_chunk + limit_chunks, chunks_total
    )

    itd_conn = connect_itd()
    checkpoint_path = get_settings().reports_dir / "import_poste_itd_checkpoint.json"
    try:
        for chunk_idx in range(start_chunk, chunks_to_run):
            start = chunk_idx * interruption_chunk_size
            batch = itd_legacy_ids[start : start + interruption_chunk_size]
            if not batch:
                break

            aggregated = _fetch_aggregated_batch(itd_conn, batch)
            stats["chunks_processed"] += 1

            for n_interruption, id_postes, poste_concerne, nombre_clients in aggregated:
                interruption_id = fk.interruption_id(n_interruption)
                if interruption_id is None:
                    stats["skipped_no_interruption"] += 1
                    continue

                poste_id = fk.poste_id_by_legacy(id_postes)
                if poste_id is None and poste_concerne:
                    poste_id = fk.poste_id(str(poste_concerne))
                if poste_id is None:
                    stats["skipped_no_poste"] += 1
                    continue

                clients = int(nombre_clients or 0)
                if clients <= 0:
                    stats["skipped_zero_clients"] += 1
                    continue

                feeder_id, service_id, poste_source_id = interruption_ctx.get(
                    int(interruption_id), (None, None, None)
                )
                pending_insert.append(
                    (
                        int(interruption_id),
                        int(poste_id),
                        clients,
                        feeder_id,
                        service_id,
                        poste_source_id,
                    )
                )

                if len(pending_insert) >= insert_batch_size:
                    inserted = _bulk_insert(
                        engine_holder,
                        pending_insert,
                        dry_run=dry_run,
                        skip_existing=skip_existing,
                    )
                    stats["inserted"] += inserted
                    pending_insert.clear()

            if not dry_run:
                checkpoint_path.write_text(
                    json.dumps(
                        {
                            "last_completed_chunk": chunk_idx,
                            "chunks_total": chunks_total,
                            "inserted_session": stats["inserted"],
                            "updated_at": datetime.now().isoformat(),
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            if (chunk_idx - start_chunk) % 10 == 0 or chunk_idx == chunks_to_run - 1:
                print(
                    f"  chunk {chunk_idx + 1}/{chunks_total} — "
                    f"insérés={stats['inserted']} rejets_poste={stats['skipped_no_poste']}",
                    flush=True,
                )
    finally:
        itd_conn.close()

    if pending_insert:
        stats["inserted"] += _bulk_insert(
            engine_holder,
            pending_insert,
            dry_run=dry_run,
            skip_existing=skip_existing,
        )

    engine = engine_holder[0]

    if not dry_run:
        try:
            with engine.begin() as conn:
                result = conn.execute(text(CONTEXT_BACKFILL_SQL))
                stats["context_backfill_rowcount"] = result.rowcount
        except OperationalError as exc:
            stats["context_backfill_error"] = str(exc)

    try:
        with engine.connect() as conn:
            stats["poste_interruptions_count"] = int(
                conn.execute(text("SELECT COUNT(*) FROM dbo.poste_interruptions")).scalar_one()
            )
            ctx = conn.execute(
                text(
                    """
                    SELECT
                        SUM(CASE WHEN feeder_id IS NULL THEN 1 ELSE 0 END) AS null_feeder,
                        SUM(CASE WHEN service_id IS NULL THEN 1 ELSE 0 END) AS null_service,
                        SUM(CASE WHEN poste_source_id IS NULL THEN 1 ELSE 0 END) AS null_poste_source
                    FROM dbo.poste_interruptions
                    """
                )
            ).mappings().one()
            stats["null_feeder_id"] = int(ctx["null_feeder"] or 0)
            stats["null_service_id"] = int(ctx["null_service"] or 0)
            stats["null_poste_source_id"] = int(ctx["null_poste_source"] or 0)
    except OperationalError:
        stats["poste_interruptions_count"] = "unavailable"
    engine.dispose()

    stats["duration_seconds"] = round(time.perf_counter() - started, 2)
    return stats


def _write_report(stats: dict[str, Any]) -> Path:
    settings = get_settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = settings.reports_dir / f"import_poste_interruptions_itd_{stamp}.json"
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import PosteInterruption ITD → SIRV2 poste_interruptions"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    mode.add_argument("--execute", action="store_true", help="Écriture en base SIRV2")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Vide poste_interruptions avant import (avec --execute)",
    )
    parser.add_argument(
        "--all-types",
        action="store_true",
        help="Inclure transport/OMVG (défaut : distribution uniquement)",
    )
    parser.add_argument(
        "--interruption-chunk-size",
        type=int,
        default=80,
        help="Nombre de NInterruption par requête ITD (défaut 80)",
    )
    parser.add_argument(
        "--insert-batch-size",
        type=int,
        default=2000,
        help="Taille des lots INSERT SQL Server (défaut 2000)",
    )
    parser.add_argument(
        "--limit-chunks",
        type=int,
        default=None,
        help="Limite le nombre de chunks (tests)",
    )
    parser.add_argument(
        "--start-chunk",
        type=int,
        default=0,
        help="Index de chunk de départ (0-based, reprise après échec)",
    )
    parser.add_argument(
        "--depuis",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d"),
        default=None,
        help="Delta : seulement les interruptions apparues depuis cette date (AAAA-MM-JJ)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reprise : pas de truncate, ignore les doublons (interruption_id, poste_id)",
    )
    args = parser.parse_args()

    dry_run = args.dry_run
    if args.truncate and dry_run:
        print("Attention : --truncate ignoré en mode --dry-run")
    if args.truncate and args.resume:
        print("Attention : --truncate ignoré avec --resume")

    start_chunk = max(0, args.start_chunk)
    if args.resume and start_chunk == 0:
        checkpoint = get_settings().reports_dir / "import_poste_itd_checkpoint.json"
        if checkpoint.is_file():
            data = json.loads(checkpoint.read_text(encoding="utf-8"))
            start_chunk = int(data.get("last_completed_chunk", -1)) + 1
            print(f"Reprise auto depuis chunk {start_chunk + 1} (checkpoint)", flush=True)

    print(
        f"Import PosteInterruption ITD -> SIRV2 "
        f"({'dry-run' if dry_run else 'EXECUTE'})…",
        flush=True,
    )
    stats = run_import(
        dry_run=dry_run,
        truncate=args.truncate and not dry_run and not args.resume,
        resume=args.resume or args.start_chunk > 0,
        start_chunk=start_chunk,
        distribution_only=not args.all_types,
        interruption_chunk_size=args.interruption_chunk_size,
        insert_batch_size=args.insert_batch_size,
        limit_chunks=args.limit_chunks,
        depuis=args.depuis,
    )
    report_path = _write_report(stats)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"Rapport : {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
