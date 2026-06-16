#!/usr/bin/env python3
"""ETL HFSQL → SIR — squelette Sprint 10."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_export(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def transform_interruptions(rows: list[dict]) -> list[dict]:
    """Mappe les champs HFSQL vers le schéma SIR."""
    out: list[dict] = []
    for row in rows:
        out.append(
            {
                "numero_interruption": row.get("NUM_INT"),
                "date_apparition": row.get("DATE_APP"),
                "cause_code": row.get("CAUSE"),
                "feeder_code": row.get("FEEDER"),
                "statut": "archive",
            }
        )
    return out


def run(dry_run: bool, source_dir: Path) -> int:
    interruptions = load_export(source_dir / "interruptions.json")
    transformed = transform_interruptions(interruptions)
    report = {
        "dry_run": dry_run,
        "source_rows": len(interruptions),
        "target_rows": len(transformed),
        "status": "ok" if transformed or not interruptions else "empty_source",
    }
    print(json.dumps(report, indent=2))
    if dry_run:
        print("Mode dry-run — aucune écriture DB.", file=sys.stderr)
        return 0
    print("Import DB non implémenté — brancher SQLAlchemy session ici.", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL migration HFSQL")
    parser.add_argument("--dry-run", action="store_true", help="Simulation sans écriture")
    parser.add_argument("--execute", action="store_true", help="Exécuter l'import")
    parser.add_argument(
        "--source",
        type=Path,
        default=ROOT / "scripts" / "migration" / "exports",
        help="Répertoire des exports JSON HFSQL",
    )
    args = parser.parse_args()
    dry_run = not args.execute
    return run(dry_run=dry_run, source_dir=args.source)


if __name__ == "__main__":
    raise SystemExit(main())
