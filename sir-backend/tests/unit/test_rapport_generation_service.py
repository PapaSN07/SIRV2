"""Tests unitaires — service génération rapports (phase 6.6)."""

from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.models.rapports import RapportGenere
from app.models.utilisateurs import Utilisateur
from app.schemas.rapports import RapportJournalierRequest
from app.services import rapport_generation_service as svc

pytestmark = pytest.mark.asyncio


def _make_user(role: str, user_id: int = 1, scope: int | None = None) -> Utilisateur:
    from app.models.utilisateurs import Permission, Role, RolePermission, UserRole

    role_obj = Role()
    role_obj.id = 1
    role_obj.nom = role
    role_obj.description = role
    role_obj.is_active = True
    perm = Permission()
    perm.id = 1
    perm.ressource = "rapports"
    perm.action = "read"
    rp = RolePermission()
    rp.id = 1
    rp.role_id = 1
    rp.permission_id = 1
    rp.role = role_obj
    rp.permission = perm
    role_obj.role_permissions = [rp]

    ur = UserRole()
    ur.id = 1
    ur.utilisateur_id = user_id
    ur.role_id = 1
    ur.scope_service_id = scope
    ur.role = role_obj

    user = Utilisateur()
    user.id = user_id
    user.login = "test"
    user.user_roles = [ur]
    ur.utilisateur = user
    return user


def _make_record(**overrides) -> RapportGenere:
    record = RapportGenere()
    record.id = overrides.get("id", 1)
    record.task_id = overrides.get("task_id", "task-abc")
    record.type_rapport = overrides.get("type_rapport", "journalier")
    record.format = overrides.get("format", "pdf")
    record.statut = overrides.get("statut", "pending")
    record.file_path = overrides.get("file_path")
    record.file_name = overrides.get("file_name")
    record.error_message = overrides.get("error_message")
    record.params_json = overrides.get("params_json", '{"date": "2026-06-12"}')
    record.region_id = overrides.get("region_id")
    record.user_id = overrides.get("user_id", 1)
    record.created_at = overrides.get("created_at", datetime.now())
    record.updated_at = record.created_at
    record.expires_at = overrides.get("expires_at", datetime.now() + timedelta(hours=24))
    return record


async def test_enqueue_journalier_enqueues_celery_task() -> None:
    user = _make_user("ADMIN_SAQS")
    db = AsyncMock()
    db.commit = AsyncMock()
    body = RapportJournalierRequest(date=date(2026, 6, 12), format="pdf")
    record = _make_record(id=42, statut="pending")

    with patch("app.repositories.rapport_repository.create_rapport", return_value=record) as create_mock, patch(
        "app.workers.tasks.rapports.generer_rapport_task.delay"
    ) as delay_mock:
        result = await svc.enqueue_journalier(db, user, body)

    create_mock.assert_awaited_once()
    delay_mock.assert_called_once_with(42)
    assert result.type_rapport == "journalier"
    assert result.statut == "pending"
    assert result.format == "pdf"
    assert create_mock.await_args.kwargs["task_id"] == result.task_id


async def test_get_status_raises_404_when_missing() -> None:
    user = _make_user("ADMIN_SAQS")
    db = AsyncMock()

    with patch("app.repositories.rapport_repository.get_by_task_id", return_value=None):
        with pytest.raises(HTTPException) as exc:
            await svc.get_status(db, user, "unknown")

    assert exc.value.status_code == 404


async def test_resolve_download_requires_success_status() -> None:
    user = _make_user("ADMIN_SAQS")
    record = _make_record(statut="pending", user_id=1)
    db = AsyncMock()

    with patch("app.repositories.rapport_repository.get_by_task_id", return_value=record):
        with pytest.raises(HTTPException) as exc:
            await svc.resolve_download(db, user, "task-abc")

    assert exc.value.status_code == 409


async def test_execute_generation_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc.settings, "rapports_storage_path", str(tmp_path))
    record = _make_record(id=7, statut="pending", type_rapport="legacy", params_json="{}")
    db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    async def _update_statut(_db, rec, **kwargs):
        for key, value in kwargs.items():
            setattr(rec, key, value)
        return rec

    with patch("redis.asyncio.from_url", return_value=mock_redis), patch(
        "app.repositories.rapport_repository.get_by_id", return_value=record
    ), patch(
        "app.repositories.rapport_repository.update_statut",
        new_callable=AsyncMock,
        side_effect=_update_statut,
    ):
        result = await svc.execute_generation(db, 7)

    assert result["statut"] == "success"
    assert record.statut == "success"
    assert record.file_path is not None
    assert Path(record.file_path).is_file()
