#!/usr/bin/env python3
"""Recalcule dbo.saifi_saidi pour toutes les périodes avec interruptions validées."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.saifi_saidi_service import recalculate_service_period


async def _list_periods(db: AsyncSession) -> list[tuple[int, int, int]]:
    result = await db.execute(
        text(
            """
            SELECT DISTINCT
                i.service_id,
                YEAR(i.date_apparition) AS annee,
                MONTH(i.date_apparition) AS mois
            FROM dbo.interruptions i
            INNER JOIN dbo.nombre_client_mois ncm
                ON ncm.service_id = i.service_id
               AND ncm.annee = YEAR(i.date_apparition)
               AND ncm.mois = MONTH(i.date_apparition)
            WHERE i.type_direction = 'distribution'
              AND i.statut = 'valide'
              AND i.service_id IS NOT NULL
            ORDER BY annee DESC, mois DESC, service_id
            """
        )
    )
    rows = result.all()
    await db.commit()
    return [(int(r[0]), int(r[1]), int(r[2])) for r in rows]


async def _recalculate_one(
    factory: async_sessionmaker[AsyncSession],
    *,
    service_id: int,
    annee: int,
    mois: int,
) -> dict:
    async with factory() as db:
        record = await recalculate_service_period(
            db,
            service_id=service_id,
            annee=annee,
            mois=mois,
        )
        await db.commit()
        return {
            "service_id": service_id,
            "annee": annee,
            "mois": mois,
            "saifi": float(record.saifi),
            "saidi": float(record.saidi),
            "nombre_interruptions": record.nombre_interruptions,
        }


async def run_recalculate(
    *,
    dry_run: bool,
    limit: int | None,
    annee: int | None,
    mois: int | None,
) -> dict:
    from app.core.config import settings as app_settings

    engine = create_async_engine(app_settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    stats: dict = {
        "dry_run": dry_run,
        "calculated": 0,
        "skipped_no_clients_ref": 0,
        "errors": 0,
        "samples": [],
    }

    async with factory() as db:
        periods = await _list_periods(db)
    if annee is not None:
        periods = [p for p in periods if p[1] == annee]
    if mois is not None:
        periods = [p for p in periods if p[2] == mois]
    if limit is not None:
        periods = periods[:limit]

    stats["periods_total"] = len(periods)

    for service_id, periode_annee, periode_mois in periods:
        if dry_run:
            stats["calculated"] += 1
            continue
        try:
            sample = await _recalculate_one(
                factory,
                service_id=service_id,
                annee=periode_annee,
                mois=periode_mois,
            )
            stats["calculated"] += 1
            if len(stats["samples"]) < 8:
                stats["samples"].append(sample)
        except ValueError:
            stats["skipped_no_clients_ref"] += 1
        except Exception as exc:
            stats["errors"] += 1
            if stats["errors"] <= 5:
                stats.setdefault("error_messages", []).append(str(exc))

    await engine.dispose()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Recalcul batch SAIFI/SAIDI")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Limite de périodes")
    parser.add_argument("--annee", type=int, default=None, help="Filtrer sur l'année")
    parser.add_argument("--mois", type=int, default=None, help="Filtrer sur le mois")
    args = parser.parse_args()

    ensure_dirs()
    stats = asyncio.run(
        run_recalculate(
            dry_run=args.dry_run,
            limit=args.limit,
            annee=args.annee,
            mois=args.mois,
        )
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = get_settings().reports_dir / f"recalculate_saifi_saidi_{stamp}.json"
    report.write_text(json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"Rapport : {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
