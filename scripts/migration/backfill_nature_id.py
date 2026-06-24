#!/usr/bin/env python3
"""Rétro-lien nature_id sur interruptions déjà importées (id_maps + exports JSONL)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.id_maps import IdMapStore
from scripts.migration.config import get_settings
from scripts.migration.hfsql_odbc import iter_table_rows
from scripts.migration.transforms.codes import text_key
from scripts.migration.transforms.rows import row_get
from sqlalchemy import create_engine, text

INTERRUPTION_TABLES = (
    "Interruptions",
    "Interruptions_Histo",
    "InterruptionsTransport",
)


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_updates() -> dict[int, int]:
    settings = get_settings()
    id_maps = IdMapStore(settings.id_maps_dir)
    inter_map = id_maps.load("interruptions")
    sir_to_nature: dict[int, int] = {}
    unmatched = 0
    no_nature_text = 0

    for table in INTERRUPTION_TABLES:
        for row in iter_table_rows(table, allow_live=True):
            legacy_id = row_get(row, "NInterruption", "ninterruption")
            if legacy_id is None:
                continue
            sir_id = inter_map.get(str(legacy_id))
            if sir_id is None:
                continue
            nature_id = None
            legacy_nature = row_get(row, "idnature", "IDNature", "id_nature")
            if legacy_nature is not None:
                try:
                    if int(legacy_nature) > 0:
                        nature_id = id_maps.get("natures", legacy_nature)
                except (TypeError, ValueError):
                    pass
            if nature_id is None:
                nature_text = row_get(row, "Nature", "nature", "naturepresumee", "NaturePresumee")
                key = text_key(str(nature_text) if nature_text is not None else None)
                if not key:
                    no_nature_text += 1
                    continue
                nature_id = id_maps.lookup_text("natures_by_text", key)
            if nature_id is None:
                unmatched += 1
                continue
            sir_to_nature[int(sir_id)] = int(nature_id)

    print(
        json.dumps(
            {
                "to_update": len(sir_to_nature),
                "unmatched_nature_text": unmatched,
                "no_nature_text": no_nature_text,
            },
            indent=2,
        )
    )
    return sir_to_nature


def apply_updates(updates: dict[int, int], batch_size: int = 2000) -> int:
    from app.core.config import settings as app_settings

    url = app_settings.database_url.replace("aioodbc", "pyodbc")
    engine = create_engine(url)
    items = list(updates.items())
    updated = 0
    for i in range(0, len(items), batch_size):
        chunk = items[i : i + batch_size]
        values_sql = ",".join(f"({sir_id},{nature_id})" for sir_id, nature_id in chunk)
        sql = (
            "UPDATE i SET nature_id = v.nature_id "
            f"FROM dbo.interruptions i "
            f"INNER JOIN (VALUES {values_sql}) AS v(id, nature_id) ON i.id = v.id "
            "WHERE i.nature_id IS NULL OR i.nature_id <> v.nature_id"
        )
        with engine.begin() as conn:
            conn.execute(text(sql))
        updated += len(chunk)
        print(f"  … {updated}/{len(items)}", flush=True)
    return updated


def main() -> int:
    updates = collect_updates()
    if not updates:
        print("Aucune mise à jour à appliquer.", file=sys.stderr)
        return 1
    n = apply_updates(updates)
    print(json.dumps({"updated": n}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
