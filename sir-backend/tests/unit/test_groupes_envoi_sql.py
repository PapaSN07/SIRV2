"""Groupes d'envoi : comptage des destinataires joignables (SQLite) et T-SQL valide."""

import pytest
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.models.notifications import Destinataire, GroupeEnvoi
from app.repositories import destinataire_repository as repo


def _query(scope: list[int] | None):
    return repo.build_list_query(
        service_id=None, is_active=True, service_ids_scope=scope, region_id_scope=None, force_service_id=None
    )


@pytest.mark.asyncio
async def test_list_groupes_envoi_compte_le_perimetre() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.exec_driver_sql("CREATE TABLE groupes_envoi (id INTEGER PRIMARY KEY, libelle TEXT, is_active BOOLEAN)")
        await conn.exec_driver_sql(
            "CREATE TABLE destinataires (id INTEGER PRIMARY KEY, utilisateur_id INT, nom TEXT, telephone TEXT, "
            "email TEXT, service_id INT, is_active BOOLEAN, fonction TEXT, groupe_id INT)"
        )
        await conn.exec_driver_sql("INSERT INTO groupes_envoi VALUES (1,'DR DAKAR',1),(2,'DIRECTION',1),(3,'ANCIEN',0)")
        await conn.exec_driver_sql(
            "INSERT INTO destinataires VALUES "
            "(1,NULL,'A','771',NULL,1,1,'Chef',1),(2,NULL,'B','772',NULL,2,1,NULL,1),"
            "(3,NULL,'C',NULL,'c@x',1,1,NULL,1),(4,NULL,'D','774',NULL,1,0,NULL,2),(5,NULL,'E','775',NULL,1,1,NULL,2)"
        )
    async with AsyncSession(engine) as db:
        # schéma dbo absent sous SQLite
        await db.connection(execution_options={"schema_translate_map": {"dbo": None}})
        national = await repo.list_groupes_envoi(db, _query(None))
        service1 = await repo.list_groupes_envoi(db, _query([1]))
    await engine.dispose()
    assert national == [(2, "DIRECTION", 1), (1, "DR DAKAR", 2)]
    assert service1 == [(2, "DIRECTION", 1), (1, "DR DAKAR", 1)]


def test_requete_groupes_sans_is_1() -> None:
    perimetre = _query([1]).with_only_columns(Destinataire.id).subquery()
    sql = str(GroupeEnvoi.__table__.select().where(GroupeEnvoi.id.in_(perimetre.select())).compile(dialect=mssql.dialect()))
    assert " IS 1" not in sql
