"""Requêtes de la base clients compilées pour SQL Server (SQLite accepte ce que mssql refuse)."""

import pytest
from sqlalchemy.dialects import mssql

from app.repositories import clients_repository as repo


class _Capture:
    def __init__(self) -> None:
        self.sql: list[str] = []

    async def execute(self, stmt, *args, **kwargs):
        self.sql.append(str(stmt.compile(dialect=mssql.dialect())))

        class _R:
            def all(self):
                return []

        return _R()


@pytest.mark.asyncio
async def test_resume_sans_sous_requete_dans_un_agregat() -> None:
    db = _Capture()
    await repo.resume_periodes(db)  # type: ignore[arg-type]
    sql = db.sql[0].upper()
    # erreur SQL Server 130 : pas de SELECT à l'intérieur d'un SUM(...)
    for morceau in sql.split("SUM(")[1:]:
        assert "SELECT" not in morceau.split(") AS")[0]
    assert "LEFT OUTER JOIN" in sql
