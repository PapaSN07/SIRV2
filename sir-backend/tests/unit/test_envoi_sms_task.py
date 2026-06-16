"""Tests unitaires — tâche Celery envoi_sms."""

from unittest.mock import patch

from app.workers.tasks import notifications as tasks


def test_envoi_sms_task_delegates_to_async_runner() -> None:
    with patch("app.workers.tasks.notifications.asyncio.run", return_value={"statut": "envoye"}) as mock_run:
        result = tasks.envoi_sms_task.run(42)
    assert result == {"statut": "envoye"}
    mock_run.assert_called_once()
