#!/usr/bin/env python3
"""Lie workflows.troncon_sig_id (étape tronçonnement) via Troncon_SIG HFSQL.

Stratégie (srv-hfsql / dbo.troncons_sig) :
1. ID_Troncon_SIG sur Interruptions si renseigné (via id_maps troncons_sig)
2. Sinon correspondance NomTroncon interruption ↔ NomTroncon / nœuds SIG + feeder

Usage :
    python scripts/migration/backfill_workflow_troncon_sig.py --dry-run
    python scripts/migration/backfill_workflow_troncon_sig.py --execute
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.hfsql_odbc import iter_table_rows
from scripts.migration.id_maps import IdMapStore
from scripts.migration.sig_troncon_matcher import (
    SigTronconRow,
    feeder_nom_aliases,
    interruption_localisation_keys,
    normalize_troncon_label,
    sig_troncon_keys,
)
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings

TRONC = "(SELECT id FROM dbo.etapes_workflow WHERE code = 'tronconnement')"


def _url() -> str:
    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def _resolve_legacy_sig_id(id_maps: IdMapStore, legacy_sig: Any) -> int | None:
    try:
        lid = int(legacy_sig)
    except (TypeError, ValueError):
        return None
    if lid <= 0:
        return None
    mapped = id_maps.get("troncons_sig", lid)
    return int(mapped) if mapped is not None else None


def _collect_legacy_sig_by_interruption(id_maps: IdMapStore) -> dict[int, int]:
    """NInterruption → sir troncon_sig_id quand ID_Troncon_SIG HFSQL > 0."""
    out: dict[int, int] = {}
    for row in iter_table_rows("Interruptions", allow_live=True):
        legacy_int = row_get(row, "NInterruption", "ninterruption")
        sir_int = id_maps.get("interruptions", legacy_int)
        if sir_int is None:
            continue
        legacy_sig = row_get(
            row,
            "ID_Troncon_SIG",
            "IDTronconSIG",
            "id_troncon_sig",
            "idtronconsig",
        )
        sir_sig = _resolve_legacy_sig_id(id_maps, legacy_sig)
        if sir_sig is not None:
            out[int(sir_int)] = sir_sig
    return out


def _build_sig_index(engine) -> tuple[dict[tuple[int, str], int], dict[tuple[str, str], int]]:
    """Index (feeder_id, clé) et (nom_feeder, clé) → troncons_sig.id (plus récent)."""
    by_feeder_id: dict[tuple[int, str], tuple[datetime | None, int]] = {}
    by_feeder_nom: dict[tuple[str, str], tuple[datetime | None, int]] = {}

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, feeder_id, nom_feeder, nom_troncon,
                       nom_noeud_amont, nom_noeud_aval, date_chargement
                FROM dbo.troncons_sig
                """
            )
        ).mappings().all()

    for row in rows:
        sig = SigTronconRow(
            id=int(row["id"]),
            feeder_id=int(row["feeder_id"]) if row["feeder_id"] is not None else None,
            nom_feeder=row["nom_feeder"],
            nom_troncon=row["nom_troncon"],
            nom_noeud_amont=row["nom_noeud_amont"],
            nom_noeud_aval=row["nom_noeud_aval"],
            date_chargement=row["date_chargement"],
        )
        keys = sig_troncon_keys(sig)
        if not keys:
            continue
        for key in keys:
            if sig.feeder_id is not None:
                _index_put(by_feeder_id, (sig.feeder_id, key), sig.date_chargement, sig.id)
            if sig.nom_feeder:
                nom = sig.nom_feeder.strip().upper()
                _index_put(by_feeder_nom, (nom, key), sig.date_chargement, sig.id)

    return (
        {k: v[1] for k, v in by_feeder_id.items()},
        {k: v[1] for k, v in by_feeder_nom.items()},
    )


def _index_put(
    store: dict[tuple[Any, str], tuple[datetime | None, int]],
    key: tuple[Any, str],
    dt: datetime | None,
    sig_id: int,
) -> None:
    prev = store.get(key)
    if prev is None or (dt or datetime.min) >= (prev[0] or datetime.min):
        store[key] = (dt, sig_id)


def _lookup_sig_id(
    *,
    feeder_id: int | None,
    feeder_libelle: str | None,
    feeder_code: str | None,
    localisation: str | None,
    by_feeder_id: dict[tuple[int, str], int],
    by_feeder_nom: dict[tuple[str, str], int],
) -> int | None:
    if not localisation:
        return None
    keys = interruption_localisation_keys(localisation)
    if not keys:
        return None

    def _try_keys(feeder_key: int | str, store: dict) -> int | None:
        for key in keys:
            hit = store.get((feeder_key, key))
            if hit is not None:
                return hit
        return None

    if feeder_id is not None:
        hit = _try_keys(feeder_id, by_feeder_id)
        if hit is not None:
            return hit

    for alias in feeder_nom_aliases(feeder_libelle, feeder_code):
        hit = _try_keys(alias, by_feeder_nom)
        if hit is not None:
            return hit
    return None


def _sql_backfill(conn) -> dict[str, int]:
    """Mise à jour bulk via jointure NomTroncon ↔ Troncon_SIG + feeder."""
    updated = conn.execute(
        text(
            f"""
            WITH candidates AS (
                SELECT
                    i.id AS interruption_id,
                    ts.id AS troncon_sig_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY i.id
                        ORDER BY ts.date_chargement DESC, ts.id DESC
                    ) AS rn
                FROM dbo.interruptions i
                INNER JOIN dbo.feeders f ON f.id = i.feeder_id
                INNER JOIN dbo.troncons_sig ts ON (
                    ts.feeder_id = f.id
                    OR UPPER(ts.nom_feeder) = UPPER(f.libelle)
                    OR UPPER(ts.nom_feeder) = UPPER(f.code)
                    OR UPPER(f.libelle) LIKE UPPER(ts.nom_feeder) + ' %'
                    OR UPPER(f.code) LIKE UPPER(ts.nom_feeder) + '_%'
                )
                LEFT JOIN dbo.workflows w
                    ON w.interruption_id = i.id AND w.etape_workflow_id = {TRONC}
                WHERE i.type_direction = 'distribution'
                  AND i.localisation IS NOT NULL
                  AND LEN(LTRIM(RTRIM(i.localisation))) > 3
                  AND (w.troncon_sig_id IS NULL OR w.troncon_sig_id = 0)
                  AND (
                    UPPER(REPLACE(LTRIM(RTRIM(i.localisation)), ' - ', '-'))
                      = UPPER(REPLACE(LTRIM(RTRIM(ts.nom_troncon)), ' - ', '-'))
                    OR UPPER(LTRIM(RTRIM(i.localisation)))
                      = UPPER(CONCAT(ts.nom_noeud_amont, ' - ', ts.nom_noeud_aval))
                  )
            )
            UPDATE w
            SET w.troncon_sig_id = c.troncon_sig_id
            FROM dbo.workflows w
            INNER JOIN candidates c ON c.interruption_id = w.interruption_id AND c.rn = 1
            WHERE w.etape_workflow_id = {TRONC}
            """
        )
    )
    inserted = conn.execute(
        text(
            f"""
            WITH candidates AS (
                SELECT
                    i.id AS interruption_id,
                    ts.id AS troncon_sig_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY i.id
                        ORDER BY ts.date_chargement DESC, ts.id DESC
                    ) AS rn
                FROM dbo.interruptions i
                INNER JOIN dbo.feeders f ON f.id = i.feeder_id
                INNER JOIN dbo.troncons_sig ts ON (
                    ts.feeder_id = f.id
                    OR UPPER(ts.nom_feeder) = UPPER(f.libelle)
                    OR UPPER(ts.nom_feeder) = UPPER(f.code)
                    OR UPPER(f.libelle) LIKE UPPER(ts.nom_feeder) + ' %'
                    OR UPPER(f.code) LIKE UPPER(ts.nom_feeder) + '_%'
                )
                WHERE i.type_direction = 'distribution'
                  AND i.localisation IS NOT NULL
                  AND LEN(LTRIM(RTRIM(i.localisation))) > 3
                  AND (
                    UPPER(REPLACE(LTRIM(RTRIM(i.localisation)), ' - ', '-'))
                      = UPPER(REPLACE(LTRIM(RTRIM(ts.nom_troncon)), ' - ', '-'))
                    OR UPPER(LTRIM(RTRIM(i.localisation)))
                      = UPPER(CONCAT(ts.nom_noeud_amont, ' - ', ts.nom_noeud_aval))
                  )
            )
            INSERT INTO dbo.workflows (interruption_id, etape_workflow_id, troncon_sig_id)
            SELECT c.interruption_id, {TRONC}, c.troncon_sig_id
            FROM candidates c
            LEFT JOIN dbo.workflows w
                ON w.interruption_id = c.interruption_id AND w.etape_workflow_id = {TRONC}
            WHERE c.rn = 1 AND w.id IS NULL
            """
        )
    )
    return {"updated": int(updated.rowcount), "inserted": int(inserted.rowcount)}


def run(*, dry_run: bool, limit: int | None, scan_hfsql: bool, use_sql: bool) -> dict[str, Any]:
    engine = create_engine(_url(), pool_pre_ping=True)
    id_maps = IdMapStore()
    id_maps.load("troncons_sig")

    legacy_map: dict[int, int] = {}
    if scan_hfsql:
        legacy_map = _collect_legacy_sig_by_interruption(id_maps)
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "legacy_id_troncon_sig": len(legacy_map),
        "scan_hfsql": scan_hfsql,
        "use_sql": use_sql,
    }

    if use_sql and not scan_hfsql:
        with engine.connect() as conn:
            pending = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM dbo.interruptions i
                    LEFT JOIN dbo.workflows w
                        ON w.interruption_id = i.id AND w.etape_workflow_id = {TRONC}
                    WHERE i.type_direction = 'distribution'
                      AND i.localisation IS NOT NULL
                      AND LEN(LTRIM(RTRIM(i.localisation))) > 3
                      AND (w.troncon_sig_id IS NULL OR w.troncon_sig_id = 0)
                    """
                )
            ).scalar_one()
            report["candidates"] = int(pending)
            if dry_run:
                engine.dispose()
                report["to_update"] = "sql_bulk"
                return report
            with engine.begin() as tx:
                stats = _sql_backfill(tx)
            report.update(stats)
            engine.dispose()
            return report

    by_feeder_id, by_feeder_nom = _build_sig_index(engine)
    report["sig_index_feeder_id"] = len(by_feeder_id)
    report["sig_index_feeder_nom"] = len(by_feeder_nom)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT i.id, i.feeder_id, f.libelle AS feeder_libelle, f.code AS feeder_code,
                       i.localisation, w.troncon_sig_id
                FROM dbo.interruptions i
                LEFT JOIN dbo.workflows w
                    ON w.interruption_id = i.id AND w.etape_workflow_id = {TRONC}
                LEFT JOIN dbo.feeders f ON f.id = i.feeder_id
                WHERE i.type_direction = 'distribution'
                  AND (w.troncon_sig_id IS NULL OR w.troncon_sig_id = 0)
                  AND i.localisation IS NOT NULL
                  AND LEN(LTRIM(RTRIM(i.localisation))) > 3
                ORDER BY i.id
                """
            )
        ).mappings().all()

    updates: list[tuple[int, int]] = []
    matched_legacy = 0
    matched_text = 0

    for row in rows:
        if limit is not None and len(updates) >= limit:
            break
        iid = int(row["id"])
        if iid in legacy_map:
            updates.append((iid, legacy_map[iid]))
            matched_legacy += 1
            continue
        sig_id = _lookup_sig_id(
            feeder_id=int(row["feeder_id"]) if row["feeder_id"] is not None else None,
            feeder_libelle=row["feeder_libelle"],
            feeder_code=row["feeder_code"],
            localisation=row["localisation"],
            by_feeder_id=by_feeder_id,
            by_feeder_nom=by_feeder_nom,
        )
        if sig_id is not None:
            updates.append((iid, sig_id))
            matched_text += 1

    report["candidates"] = len(rows)
    report["matched_legacy_fk"] = matched_legacy
    report["matched_nomtroncon"] = matched_text
    report["to_update"] = len(updates)

    if dry_run or not updates:
        engine.dispose()
        return report

    batch_size = 500
    updated = 0
    with engine.begin() as conn:
        for idx, (interruption_id, sig_id) in enumerate(updates, start=1):
            exists = conn.execute(
                text(
                    f"SELECT id FROM dbo.workflows "
                    f"WHERE interruption_id = :iid AND etape_workflow_id = {TRONC}"
                ),
                {"iid": interruption_id},
            ).scalar_one_or_none()
            if exists is None:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO dbo.workflows (interruption_id, etape_workflow_id, troncon_sig_id)
                        VALUES (:iid, {TRONC}, :sig)
                        """
                    ),
                    {"iid": interruption_id, "sig": sig_id},
                )
            else:
                conn.execute(
                    text(
                        f"""
                        UPDATE dbo.workflows
                        SET troncon_sig_id = :sig
                        WHERE interruption_id = :iid
                          AND etape_workflow_id = {TRONC}
                          AND (troncon_sig_id IS NULL OR troncon_sig_id <> :sig)
                        """
                    ),
                    {"iid": interruption_id, "sig": sig_id},
                )
            updated += 1
            if idx % batch_size == 0:
                print(f"  … {idx}/{len(updates)}", flush=True)

    report["updated"] = updated
    engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--scan-hfsql",
        action="store_true",
        help="Scanner Interruptions HFSQL pour ID_Troncon_SIG (lent)",
    )
    parser.add_argument(
        "--python-match",
        action="store_true",
        help="Matching Python (lent) au lieu du bulk SQL",
    )
    args = parser.parse_args()
    dry_run = args.dry_run or not args.execute
    report = run(
        dry_run=dry_run,
        limit=args.limit,
        scan_hfsql=args.scan_hfsql,
        use_sql=not args.python_match,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
