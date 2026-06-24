#!/usr/bin/env python3
"""Test prérequis migration — ODBC HFSQL + config cible."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Bootstrap avant imports package
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.migration._bootstrap  # noqa: F401
from scripts.migration.config import ensure_dirs, get_settings
from scripts.migration.hfsql_odbc import test_connection


def main() -> int:
    ensure_dirs()
    settings = get_settings()
    report = {
        "hfsql": test_connection(),
        "sir_profile": settings.sir_profile,
        "database_url_prefix": settings.database_url.split("@")[-1][:80] if settings.database_url else None,
        "cutoff_years": settings.migration_cutoff_years,
        "date_from": settings.migration_date_from or None,
        "date_to": settings.migration_date_to or None,
        "dry_run_default": settings.migration_dry_run,
    }
    out = json.dumps(report, indent=2, ensure_ascii=True)
    print(out)
    hfsql = report["hfsql"]
    ok = hfsql.get("connected") or hfsql.get("server_reachable")
    if not hfsql.get("connected"):
        print(
            "\nNote: serveur joignable — verifiez HFSQL_DATABASE ou HFSQL_DSN dans .env.migration",
            file=sys.stderr,
        )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
