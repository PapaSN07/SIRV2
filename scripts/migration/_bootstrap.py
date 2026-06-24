"""Bootstrap PYTHONPATH pour exécution directe des scripts migration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MIGRATION_ROOT = Path(__file__).resolve().parent
REPO_ROOT = MIGRATION_ROOT.parents[1]
BACKEND_ROOT = REPO_ROOT / "sir-backend"


def _load_migration_env() -> None:
    """Charge .env.migration avant tout import sir-backend (évite profil docker par défaut)."""
    for path in (REPO_ROOT / ".env.migration", MIGRATION_ROOT / ".env.migration"):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and value:
                os.environ.setdefault(key, value)
        break
    os.environ.setdefault("SIR_PROFILE", "senelec")


_load_migration_env()

for p in (str(REPO_ROOT), str(BACKEND_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
