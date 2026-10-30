"""Groupes d'envoi : comptage des membres joignables par périmètre (SQLite), plusieurs groupes par personne."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.repositories import destinataire_repository as repo


def _query(scope: list[int] | None):
    return repo.build_list_query(
        service_id=None, is_active=True, service_ids_scope=scope, region_id_scope=None, force_service_id=None
    )


@pytest.mark.asyncio
async def test_list_groupes_envoi_compte_le_perimetre() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE groupes_envoi (id INTEGER PRIMARY KEY, libelle TEXT, is_active BOOLEAN, exploitation TEXT)"
        )
        await conn.exec_driver_sql(
            "CREATE TABLE destinataires (id INTEGER PRIMARY KEY, utilisateur_id INT, nom TEXT, telephone TEXT, "
            "email TEXT, service_id INT, is_active BOOLEAN, fonction TEXT, matricule INT)"
        )
        await conn.exec_driver_sql("CREATE TABLE destinataire_groupes (destinataire_id INT, groupe_id INT)")
        await conn.exec_driver_sql(
            "INSERT INTO groupes_envoi VALUES (1,'DR DAKAR',1,'BCC'),(2,'DIRECTION',1,NULL),(3,'ANCIEN',0,NULL)"
        )
        await conn.exec_driver_sql(
            "INSERT INTO destinataires VALUES "
            "(1,NULL,'A','771',NULL,1,1,'Chef',NULL),(2,NULL,'B','772',NULL,2,1,NULL,NULL),"
            "(3,NULL,'C',NULL,'c@x',1,1,NULL,NULL),(4,NULL,'D','774',NULL,1,0,NULL,NULL),(5,NULL,'E','775',NULL,1,1,NULL,NULL)"
        )
        # A est dans les deux groupes
        await conn.exec_driver_sql(
            "INSERT INTO destinataire_groupes VALUES (1,1),(1,2),(2,1),(3,1),(4,2),(5,2),(1,3)"
        )
    async with AsyncSession(engine) as db:
        await db.connection(execution_options={"schema_translate_map": {"dbo": None}})
        national = [(g.libelle, g.exploitation, n) for g, n in await repo.list_groupes_envoi(db, _query(None))]
        service1 = [(g.libelle, n) for g, n in await repo.list_groupes_envoi(db, _query([1]))]
        tous = [g.libelle for g, _ in await repo.list_groupes_envoi(db, _query(None), inclure_inactifs=True)]
    await engine.dispose()
    assert national == [("DIRECTION", None, 2), ("DR DAKAR", "BCC", 2)]
    assert service1 == [("DIRECTION", 2), ("DR DAKAR", 1)]
    assert tous == ["ANCIEN", "DIRECTION", "DR DAKAR"]


@pytest.mark.asyncio
async def test_filtre_groupe_et_recherche() -> None:
    from sqlalchemy import select

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE destinataires (id INTEGER PRIMARY KEY, utilisateur_id INT, nom TEXT, telephone TEXT, "
            "email TEXT, service_id INT, is_active BOOLEAN, fonction TEXT, matricule INT)"
        )
        await conn.exec_driver_sql("CREATE TABLE destinataire_groupes (destinataire_id INT, groupe_id INT)")
        await conn.exec_driver_sql(
            "INSERT INTO destinataires VALUES (1,NULL,'Awa DIOP','771',NULL,NULL,1,'Chef BCC',NULL),"
            "(2,NULL,'Moussa FALL','772',NULL,NULL,1,'Technicien',NULL)"
        )
        await conn.exec_driver_sql("INSERT INTO destinataire_groupes VALUES (1,1),(2,2)")
    commun = dict(service_id=None, is_active=None, service_ids_scope=None, region_id_scope=None, force_service_id=None)
    par_groupe = repo.build_list_query(**commun, groupe_id=1).subquery()
    par_texte = repo.build_list_query(**commun, recherche="techni").subquery()
    async with AsyncSession(engine) as db:
        await db.connection(execution_options={"schema_translate_map": {"dbo": None}})
        ids_groupe = [i for (i,) in (await db.execute(select(par_groupe.c.id))).all()]
        ids_texte = [i for (i,) in (await db.execute(select(par_texte.c.id))).all()]
    await engine.dispose()
    assert ids_groupe == [1] and ids_texte == [2]
