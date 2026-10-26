"""Les tâches Celery n'utilisent jamais le pool de connexions de l'API."""

import ast
import pathlib

from sqlalchemy.pool import NullPool

from app.workers import db as worker_db

TASKS_DIR = pathlib.Path(__file__).resolve().parents[2] / "app" / "workers" / "tasks"


def test_moteur_worker_sans_pool() -> None:
    # Une connexion par session, ouverte et fermée dans la boucle asyncio.run() de la tâche
    assert isinstance(worker_db.worker_engine.pool, NullPool)


def test_aucune_tache_n_importe_la_session_de_l_api() -> None:
    fautifs = []
    for path in TASKS_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.core.database":
                fautifs.append(f"{path.name}: {[a.name for a in node.names]}")
    assert fautifs == [], f"Tâches liées au pool de l'API : {fautifs}"


async def test_echec_sms_conserve_le_statut_echec() -> None:
    """Un envoi SMS en erreur doit laisser la trace « echec » en base (commit, pas rollback)."""
    from unittest.mock import AsyncMock, MagicMock, patch

    import pytest

    from app.workers.tasks import notifications as tasks

    db = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(tasks, "WorkerSessionLocal", return_value=session_cm),
        patch.object(tasks.sms_service, "send_sms_record", AsyncMock(side_effect=RuntimeError("passerelle KO"))),
        pytest.raises(RuntimeError),
    ):
        await tasks._run_envoi_sms(42)

    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
