"""Tests unitaires — tâche Celery generer_rapport (phase 6.6)."""

from unittest.mock import patch

import pytest

from app.workers.tasks.rapports import generer_rapport_task


def test_generer_rapport_task_success() -> None:
    with patch(
        "app.workers.tasks.rapports.asyncio.run",
        return_value={"task_id": "abc", "statut": "success"},
    ) as run_mock:
        result = generer_rapport_task.run(42)

    run_mock.assert_called_once()
    assert result["statut"] == "success"


def test_generer_rapport_task_retries_on_failure() -> None:
    task = generer_rapport_task

    with patch("app.workers.tasks.rapports.asyncio.run", side_effect=RuntimeError("db down")):
        with pytest.raises(RuntimeError):
            task.run(99)
