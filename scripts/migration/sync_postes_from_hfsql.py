#!/usr/bin/env python3
"""Synchronise dbo.postes depuis HFSQL Postes (insert manquants + update FK).

Corrige notamment feeder_id / service_id / puissance_kva / libelle
qui étaient absents après le premier import (lookup Feeder texte seul).

Usage :
    python scripts/migration/sync_postes_from_hfsql.py --dry-run
    python scripts/migration/sync_postes_from_hfsql.py --execute
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
from scripts.migration.hfsql_odbc import iter_table_rows
from scripts.migration.id_maps import IdMapStore
from scripts.migration.transforms.codes import slug_code, text_key
from scripts.migration.transforms.fk_resolver import FkResolver
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

from app.core.config import settings as app_settings


def _url() -> str:
    url = app_settings.database_url.replace("mssql+aioodbc", "mssql+pyodbc")
    if "TrustServerCertificate" not in url:
        url += "&TrustServerCertificate=yes" if "?" in url else "?TrustServerCertificate=yes"
    return url


def _puissance_kva(row: dict[str, Any]) -> float | None:
    raw = row_get(row, "puissanceTransfo", "puissancetransfo")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def run(*, dry_run: bool) -> dict[str, Any]:
    id_maps = IdMapStore()
    for name in (
        "postes",
        "postes_by_text",
        "feeders",
        "feeders_by_text",
        "services",
        "services_by_text",
    ):
        id_maps.load(name)
    fk = FkResolver(id_maps)

    engine = create_engine(_url(), pool_pre_ping=True)
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "scanned": 0,
        "updated": 0,
        "inserted": 0,
        "unchanged": 0,
        "feeder_resolved": 0,
        "service_resolved": 0,
        "rejected": 0,
    }

    updates: list[dict[str, Any]] = []
    inserts: list[dict[str, Any]] = []

    with engine.connect() as conn:
        current_rows = {
            int(r["id"]): r
            for r in conn.execute(
                text(
                    """
                    SELECT id, feeder_id, service_id, libelle, puissance_kva, code, is_active
                    FROM dbo.postes
                    """
                )
            ).mappings()
        }

    for row in iter_table_rows("Postes", allow_live=True):
        report["scanned"] += 1
        legacy_id = row_get(row, "IDPostes", "idpostes")
        if legacy_id is None:
            report["rejected"] += 1
            continue
        try:
            lid = int(legacy_id)
        except (TypeError, ValueError):
            report["rejected"] += 1
            continue

        libelle = str(row_get(row, "Poste", "poste", "NomPoste") or "").strip()
        if not libelle:
            report["rejected"] += 1
            continue

        feeder_id = fk.resolve_feeder_id(row)
        service_id = fk.service_id_by_legacy(
            row_get(row, "ID_Service", "id_service", "IDService", "idservice")
        )
        if service_id is None:
            service_id = fk.service_id(str(row_get(row, "Service", "service") or ""))
        puissance_kva = _puissance_kva(row)

        if feeder_id is not None:
            report["feeder_resolved"] += 1
        if service_id is not None:
            report["service_resolved"] += 1

        sir_id = id_maps.get("postes", lid)
        if sir_id is None:
            # Cherche par code P{legacy}
            code = slug_code(str(lid), prefix="P")[:20]
            inserts.append(
                {
                    "legacy_id": lid,
                    "code": code,
                    "libelle": libelle[:200],
                    "feeder_id": feeder_id,
                    "service_id": service_id,
                    "puissance_kva": puissance_kva,
                }
            )
            continue

        sir_id = int(sir_id)
        cur = current_rows.get(sir_id)
        if cur is None:
            inserts.append(
                {
                    "legacy_id": lid,
                    "code": slug_code(str(lid), prefix="P")[:20],
                    "libelle": libelle[:200],
                    "feeder_id": feeder_id,
                    "service_id": service_id,
                    "puissance_kva": puissance_kva,
                }
            )
            continue

        needs = (
            cur.feeder_id != feeder_id
            or cur.service_id != service_id
            or (cur.libelle or "") != libelle[:200]
            or (
                (float(cur.puissance_kva) if cur.puissance_kva is not None else None)
                != puissance_kva
            )
        )
        if not needs:
            report["unchanged"] += 1
            continue

        updates.append(
            {
                "id": sir_id,
                "feeder_id": feeder_id,
                "service_id": service_id,
                "libelle": libelle[:200],
                "puissance_kva": puissance_kva,
            }
        )

    report["would_update"] = len(updates)
    report["would_insert"] = len(inserts)

    if dry_run:
        engine.dispose()
        return report

    with engine.begin() as conn:
        for u in updates:
            conn.execute(
                text(
                    """
                    UPDATE dbo.postes
                    SET feeder_id = :feeder_id,
                        service_id = :service_id,
                        libelle = :libelle,
                        puissance_kva = :puissance_kva
                    WHERE id = :id
                    """
                ),
                u,
            )
            report["updated"] += 1

        for ins in inserts:
            result = conn.execute(
                text(
                    """
                    INSERT INTO dbo.postes (
                        code, libelle, feeder_id, service_id, puissance_kva, is_active
                    )
                    OUTPUT INSERTED.id
                    VALUES (
                        :code, :libelle, :feeder_id, :service_id, :puissance_kva, 1
                    )
                    """
                ),
                ins,
            )
            new_id = int(result.scalar_one())
            id_maps.put("postes", ins["legacy_id"], new_id)
            key = text_key(ins["libelle"])
            if key:
                id_maps.put("postes_by_text", key, new_id)
            report["inserted"] += 1

    id_maps.save("postes")
    id_maps.save("postes_by_text")

    with engine.connect() as conn:
        report["after_count"] = int(conn.execute(text("SELECT COUNT(*) FROM dbo.postes")).scalar_one())
        report["after_with_feeder"] = int(
            conn.execute(
                text("SELECT COUNT(*) FROM dbo.postes WHERE feeder_id IS NOT NULL")
            ).scalar_one()
        )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
