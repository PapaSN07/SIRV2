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


def terminer(code: int | None) -> None:
    """Fin de script sans finalisation de l'interpréteur.

    Le pilote ODBC HFSQL (PC SOFT) plante souvent au déchargement, à la fermeture de Python :
    code de sortie 3221225477 (0xC0000005, violation d'accès) alors que le travail est fini et
    validé. Les scripts enchaînés (delta_periode, sync_interruptions) prenaient cela pour un échec.
    On vide les sorties puis on quitte directement avec le vrai code.
    """
    sys.stdout.flush()
    sys.stderr.flush()
    # Témoin de fin pour un script lanceur (delta_periode) : main() est allé au bout avec ce code
    marqueur = os.environ.get("MIGRATION_MARQUEUR_FIN")
    if marqueur:
        Path(marqueur).write_text(str(int(code or 0)), encoding="utf-8")
    if sys.platform == "win32":
        # os._exit passe encore par ExitProcess, qui prévient chaque DLL (dont le pilote HFSQL, qui
        # plante) ; TerminateProcess arrête le processus sans ces notifications.
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.TerminateProcess(kernel32.GetCurrentProcess(), int(code or 0))
    os._exit(int(code or 0))
