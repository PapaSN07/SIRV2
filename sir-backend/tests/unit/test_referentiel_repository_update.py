"""Non-régression : la fonction update() du repository référentiel masquait
sqlalchemy.update, ce qui faisait échouer toute modification (TypeError → 500)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy.sql.dml import Update

from app.repositories import referentiel_repository as repo

_GET_BY_ID = "app.repositories.referentiel_repository.get_by_id"


async def test_update_executes_sql_update_statement() -> None:
    db = AsyncMock()
    record = SimpleNamespace(id=1, libelle="Avant")
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=record):
        result = await repo.update(db, "causes", 1, libelle="Après")

    assert result is record
    statement = db.execute.await_args.args[0]
    assert isinstance(statement, Update)
    assert statement.table.name == repo.get_model("causes").__tablename__
    db.flush.assert_awaited_once()


async def test_soft_delete_sets_is_active_false() -> None:
    db = AsyncMock()
    record = SimpleNamespace(id=1, is_active=True)
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=record):
        await repo.soft_delete(db, "causes", 1)

    statement = db.execute.await_args.args[0]
    assert isinstance(statement, Update)
    compiled = statement.compile()
    assert compiled.params["is_active"] is False


async def test_update_unknown_id_returns_none_without_sql() -> None:
    db = AsyncMock()
    with patch(_GET_BY_ID, new_callable=AsyncMock, return_value=None):
        assert await repo.update(db, "causes", 999, libelle="x") is None
    db.execute.assert_not_awaited()
