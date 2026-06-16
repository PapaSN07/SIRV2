"""Tests unitaires — envoi email Celery."""

from unittest.mock import patch

import pytest

from app.workers.tasks.notifications import envoi_email_task


def test_envoi_email_task_success() -> None:
    with patch(
        "app.workers.tasks.notifications.asyncio.run",
        return_value={"statut": "envoye"},
    ) as mock_run:
        result = envoi_email_task.run(1)
    assert result["statut"] == "envoye"
    mock_run.assert_called_once()


def test_envoi_email_task_retries_on_error() -> None:
    with patch(
        "app.workers.tasks.notifications.asyncio.run",
        side_effect=RuntimeError("db down"),
    ):
        with pytest.raises(RuntimeError):
            envoi_email_task.run(1)
