#!/usr/bin/env python3
"""Import SousFeeders depuis HFSQL (vague reseau) + bootstrap si vide."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.bootstrap_sous_feeders import run as bootstrap_run
from scripts.migration.config import ensure_dirs
from scripts.migration.db_session import get_session
from scripts.migration.extract_hfsql import run as extract_run
from scripts.migration.loaders.reseau import ReseauLoader
from scripts.migration.loaders.referentiel import ReferentielLoader
from scripts.migration.id_maps import IdMapStore
from sqlalchemy import text


def _count_sous_feeders() -> int:
    with get_session() as session:
        return int(session.execute(text("SELECT COUNT(*) FROM dbo.sous_feeders")).scalar_one())


def main() -> int:
    parser = argparse.ArgumentParser(description="Import sous_feeders HFSQL")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Ne pas ré-extraire HFSQL (utiliser exports existants)",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Créer un sous-feeder par feeder sans passer par HFSQL",
    )
    args = parser.parse_args()
    ensure_dirs()
    dry_run = args.dry_run

    before = _count_sous_feeders()
    print(f"sous_feeders avant: {before}")

    if not args.bootstrap_only:
        if not args.skip_extract:
            print("Extraction HFSQL SousFeeder, TypeEND, TypeReseau…")
            extract_run(tables=["SousFeeder", "TypeEND", "TypeReseau"])
        id_maps = IdMapStore()
        with get_session() as session:
            loader = ReseauLoader(session=session, id_maps=id_maps, dry_run=dry_run)
            loader._load_sous_feeders()
            refs = ReferentielLoader(session=session, id_maps=id_maps, dry_run=dry_run)
            refs._load_types_end()
            refs._load_types_reseaux()
            print("types", refs.stats)
            if not dry_run:
                id_maps.save("sous_feeders")
                id_maps.save("types_end")
                id_maps.save("types_reseaux")
                real = session.execute(
                    text(
                        "SELECT COUNT(*) FROM dbo.sous_feeders "
                        "WHERE is_active = 1 AND code LIKE 'SF[0-9]%'"
                    )
                ).scalar_one()
                if int(real or 0) > 0:
                    hidden = session.execute(
                        text(
                            "UPDATE dbo.sous_feeders SET is_active = 0 "
                            "WHERE is_active = 1 AND libelle LIKE N'%sous-feeder' "
                            "AND code NOT LIKE 'SF[0-9]%'"
                        )
                    ).rowcount
                    print(f"sous-feeders de repli désactivés: {hidden}")

    after_hfsql = _count_sous_feeders()
    print(f"sous_feeders après HFSQL: {after_hfsql}")

    if after_hfsql == 0 or args.bootstrap_only:
        print("Bootstrap sous-feeders depuis feeders…")
        stats = bootstrap_run(dry_run=dry_run)
        print(stats)

    after = _count_sous_feeders()
    print(f"sous_feeders final: {after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
