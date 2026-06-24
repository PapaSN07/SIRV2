#!/usr/bin/env python3
"""Orchestrateur ETL HFSQL → SQL Server SIRV2."""

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
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.db_session import get_session
from scripts.migration.id_maps import IdMapStore
from scripts.migration.loaders.geo import GeoLoader
from scripts.migration.loaders.indicateurs import IndicateursLoader
from scripts.migration.loaders.interruptions import InterruptionsLoader
from scripts.migration.loaders.napt import NaptLoader
from scripts.migration.loaders.referentiel import ReferentielLoader
from scripts.migration.loaders.reseau import ReseauLoader
from scripts.migration.loaders.utilisateurs import UtilisateursLoader

WAVES: dict[str, list] = {
    "geo": [GeoLoader],
    "referentiel": [ReferentielLoader],
    "reseau": [ReseauLoader],
    "utilisateurs": [UtilisateursLoader],
    "interruptions": [InterruptionsLoader],
    "indicateurs": [IndicateursLoader],
    "napt": [NaptLoader],
}


def run_wave(wave: str, dry_run: bool) -> list[dict[str, Any]]:
    if wave not in WAVES:
        raise ValueError(f"Vague inconnue: {wave}. Choix: {', '.join(WAVES)}")
    ensure_dirs()
    id_maps = IdMapStore()
    results: list[dict[str, Any]] = []
    system_user_id = 1

    with get_session() as session:
        if wave in ("utilisateurs", "interruptions", "napt") and wave == "utilisateurs":
            pass
        for loader_cls in WAVES[wave]:
            kwargs: dict[str, Any] = {}
            if loader_cls in (InterruptionsLoader, NaptLoader):
                kwargs["system_user_id"] = system_user_id
            loader = loader_cls(session, id_maps, dry_run=dry_run, **kwargs)
            if loader_cls is UtilisateursLoader and not dry_run:
                result = loader.run()
                system_user_id = loader.system_user_id()
            else:
                result = loader.run()
            results.append(result)
            loader.flush_batch()
    return results


def run_all(dry_run: bool, waves: list[str] | None = None) -> dict[str, Any]:
    selected = waves or list(WAVES.keys())
    ensure_dirs()
    id_maps = IdMapStore()
    all_results: dict[str, Any] = {"dry_run": dry_run, "waves": {}}
    system_user_id = 1

    with get_session() as session:
        for wave in selected:
            wave_results: list[dict[str, Any]] = []
            for loader_cls in WAVES[wave]:
                kwargs: dict[str, Any] = {}
                if loader_cls in (InterruptionsLoader, NaptLoader):
                    kwargs["system_user_id"] = system_user_id
                loader = loader_cls(session, id_maps, dry_run=dry_run, **kwargs)
                result = loader.run()
                if isinstance(loader, UtilisateursLoader):
                    system_user_id = loader.system_user_id()
                wave_results.append(result)
                loader.flush_batch()
            all_results["waves"][wave] = wave_results
    return all_results


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="ETL migration HFSQL → SIRV2")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    parser.add_argument("--execute", action="store_true", help="Exécuter l'import réel")
    parser.add_argument(
        "--wave",
        choices=list(WAVES.keys()) + ["all"],
        default="all",
        help="Vague ETL à exécuter",
    )
    args = parser.parse_args()
    dry_run = not args.execute if args.execute else (args.dry_run or settings.migration_dry_run)
    waves = None if args.wave == "all" else [args.wave]
    try:
        if args.wave == "all" and waves is None:
            report = run_all(dry_run=dry_run)
        else:
            report = {"dry_run": dry_run, "waves": {args.wave: run_wave(args.wave, dry_run)}}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
