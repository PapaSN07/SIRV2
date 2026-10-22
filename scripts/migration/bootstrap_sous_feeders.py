#!/usr/bin/env python3
"""Crée un sous-feeder par feeder actif si la table est vide ou incomplète.

Usage :
    python scripts/migration/bootstrap_sous_feeders.py --dry-run
    python scripts/migration/bootstrap_sous_feeders.py --execute
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import get_settings
from scripts.migration.db_session import get_session
from scripts.migration.transforms.codes import slug_code
from sqlalchemy import select, text

from app.models.reseau import Feeder, SousFeeder


def run(*, dry_run: bool) -> dict[str, int]:
    stats = {"feeders": 0, "created": 0, "skipped": 0}
    with get_session() as session:
        feeders = session.execute(
            select(Feeder.id, Feeder.code, Feeder.libelle).where(Feeder.is_active == True)  # noqa: E712
        ).all()
        stats["feeders"] = len(feeders)
        existing_by_feeder = {
            int(row[0]): int(row[1])
            for row in session.execute(
                text(
                    "SELECT feeder_id, COUNT(*) FROM dbo.sous_feeders "
                    "WHERE is_active = 1 GROUP BY feeder_id"
                )
            ).all()
        }

        for feeder_id, code, libelle in feeders:
            feeder_id = int(feeder_id)
            if existing_by_feeder.get(feeder_id, 0) > 0:
                stats["skipped"] += 1
                continue
            sf_code = slug_code(f"{code}_SF")[:20]
            sf_libelle = f"{libelle} — sous-feeder"[:200]
            if dry_run:
                stats["created"] += 1
                continue
            exists = session.execute(
                select(SousFeeder.id).where(SousFeeder.code == sf_code)
            ).scalar_one_or_none()
            if exists:
                stats["skipped"] += 1
                continue
            session.add(
                SousFeeder(
                    feeder_id=feeder_id,
                    code=sf_code,
                    libelle=sf_libelle,
                    is_active=True,
                )
            )
            stats["created"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap sous_feeders depuis feeders")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    stats = run(dry_run=args.dry_run)
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
