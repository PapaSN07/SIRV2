"""Tests unitaires — tâche Celery calcul_saifi_saidi (phase 5.1)."""

from unittest.mock import AsyncMock, patch

from app.workers.tasks.indicateurs import calcul_saifi_saidi_task


def test_calcul_saifi_saidi_task_returns_calculated_status() -> None:
    expected = {
        "interruption_id": 42,
        "status": "calculated",
        "service_id": 1,
        "annee": 2026,
        "mois": 6,
        "saifi": 0.02,
        "saidi": 1.5,
        "nombre_interruptions": 3,
        "total_clients_reference": 50000,
        "region_id": 2,
    }

    with patch(
        "app.workers.tasks.indicateurs._run_calcul_saifi_saidi",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        result = calcul_saifi_saidi_task.run(42)

    assert result == expected


def test_calcul_saifi_saidi_task_skipped_non_distribution() -> None:
    expected = {
        "interruption_id": 99,
        "status": "skipped_not_distribution",
        "service_id": None,
    }

    with patch(
        "app.workers.tasks.indicateurs._run_calcul_saifi_saidi",
        new_callable=AsyncMock,
        return_value=expected,
    ):
        result = calcul_saifi_saidi_task.run(99)

    assert result["status"] == "skipped_not_distribution"
