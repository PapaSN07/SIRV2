"""Tests unitaires — tâche Celery calcul_end (phase 3.8)."""

from unittest.mock import AsyncMock, patch

from app.workers.tasks.indicateurs import calcul_end_task


def test_calcul_end_task_returns_calculated_status() -> None:
    expected = {
        "interruption_id": 42,
        "status": "calculated",
        "valeur_mwh": 10.0,
        "est_force_majeure": False,
        "type_end_id": 1,
        "region_id": 2,
    }

    mock_self = type("Task", (), {"retry": lambda *a, **k: None})()

    with patch(
        "app.workers.tasks.indicateurs._run_calcul_end",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        result = calcul_end_task.run(42)

    assert result == expected
