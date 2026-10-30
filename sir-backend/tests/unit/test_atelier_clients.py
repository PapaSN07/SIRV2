"""Atelier clients : proposer / valider / rejeter un lien poste ↔ UR, périmètre régional, recalcul."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.schemas.base_clients import LienPosteURCreate
from app.services import atelier_clients_service as atelier


def _user(uid: int, role: str, region: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(id=uid, user_roles=[SimpleNamespace(role=SimpleNamespace(nom=role), scope_service_id=region)])


BCC = _user(1, "BCC", 10)
BRC = _user(2, "BRC", 10)
BRC_AUTRE = _user(3, "BRC", 20)
SAQS = _user(4, "ADMIN_SAQS")


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    async with engine.begin() as c:
        for ddl in (
            "CREATE TABLE services (id INTEGER PRIMARY KEY, region_id INT, libelle TEXT)",
            "CREATE TABLE postes (id INTEGER PRIMARY KEY, code TEXT, libelle TEXT, service_id INT, nombre_clients INT)",
            "CREATE TABLE utilisateurs (id INTEGER PRIMARY KEY, prenom TEXT, nom TEXT)",
            "CREATE TABLE contrats_unites_releve (id INTEGER PRIMARY KEY, annee INT, mois INT, unite_releve TEXT, "
            "libelle TEXT, code_agence TEXT, delegation TEXT, agence_id INT, nb_contrats INT, date_maj DATETIME, "
            "source TEXT)",
            "CREATE TABLE postes_unites_releve (id INTEGER PRIMARY KEY, poste_id INT, unite_releve TEXT, statut TEXT, "
            "modifie_par_id INT, modifie_le DATETIME, valide_par_id INT, valide_le DATETIME, "
            "UNIQUE (poste_id, unite_releve))",
            "INSERT INTO services VALUES (5, 10, 'Bourguiba'), (6, 20, 'Thiès')",
            "INSERT INTO postes VALUES (100, 'P100', 'Poste A', 5, 0), (101, 'P101', 'Poste B', 5, 0), "
            "(200, 'P200', 'Poste Thiès', 6, 0)",
            "INSERT INTO utilisateurs VALUES (1, 'Awa', 'Ndiaye'), (2, 'Moussa', 'Fall')",
            "INSERT INTO contrats_unites_releve (annee, mois, unite_releve, libelle, nb_contrats, source) VALUES "
            "(2026, 9, '1100200I', 'ancien', 1, 'fichier'), (2026, 10, '1100200I', 'Bourguiba 0200', 100, 'bi_ods'), "
            "(2026, 10, '1100201P', 'Bourguiba 0201', 30, 'bi_ods')",
            "INSERT INTO postes_unites_releve (id, poste_id, unite_releve, statut) VALUES (1, 100, '1100200I', 'valide')",
        ):
            await c.exec_driver_sql(ddl)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def _statuts(db: AsyncSession) -> dict[tuple[int, str], str]:
    rows = await db.execute(text("SELECT poste_id, unite_releve, statut FROM postes_unites_releve"))
    return {(p, u): s for p, u, s in rows.all()}


@pytest.mark.asyncio
async def test_proposer_puis_valider_ajout(db: AsyncSession) -> None:
    lien_id = await atelier.proposer_ajout(db, BCC, LienPosteURCreate(poste_id=101, unite_releve=" 1100200i "))
    assert (await _statuts(db))[(101, "1100200I")] == "ajout_propose"
    # le BCC ne valide pas
    with pytest.raises(HTTPException) as exc:
        await atelier.decider(db, BCC, lien_id, accepter=True)
    assert exc.value.status_code == 403
    message, postes = await atelier.decider(db, BRC, lien_id, accepter=True)
    assert message == "Ajout validé" and sorted(postes) == [100, 101]
    assert (await _statuts(db))[(101, "1100200I")] == "valide"

    # UR partagée : 100 contrats répartis entre les deux postes, au dernier mois chargé
    bilan = await atelier.recalculer_postes(db, postes)
    assert bilan["periode"] == "10/2026" and bilan["postes"] == {100: 50, 101: 50}

    page = await atelier.lister(db, BRC, poste_id=101, a_valider=False, recherche=None, page=1, page_size=50)
    lien = page.items[0]
    assert (lien.nb_contrats, lien.nb_postes, lien.modifie_par, lien.valide_par) == (100, 2, "Awa Ndiaye", "Moussa Fall")


@pytest.mark.asyncio
async def test_retrait_et_rejet(db: AsyncSession) -> None:
    assert await atelier.proposer_retrait(db, BCC, 1) == "Retrait proposé, en attente de validation"
    # tant que le retrait n'est pas validé, l'UR compte encore
    assert (await atelier.recalculer_postes(db, [100]))["postes"] == {100: 100}
    message, postes = await atelier.decider(db, BRC, 1, accepter=False)
    assert message == "Retrait rejeté" and postes == []
    assert (await _statuts(db))[(100, "1100200I")] == "valide"

    await atelier.proposer_retrait(db, BRC, 1)
    message, postes = await atelier.decider(db, BRC, 1, accepter=True)
    assert message == "Retrait validé" and postes == [100]
    assert await _statuts(db) == {}
    # plus aucune UR : le poste retombe à 0 client
    assert (await atelier.recalculer_postes(db, postes))["postes"] == {100: 0}


@pytest.mark.asyncio
async def test_annuler_ajout_et_doublon(db: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc:
        await atelier.proposer_ajout(db, BCC, LienPosteURCreate(poste_id=100, unite_releve="1100200I"))
    assert exc.value.status_code == 409
    lien_id = await atelier.proposer_ajout(db, BCC, LienPosteURCreate(poste_id=100, unite_releve="1100201P"))
    assert await atelier.proposer_retrait(db, BCC, lien_id) == "Proposition d'ajout annulée"
    assert (100, "1100201P") not in await _statuts(db)


@pytest.mark.asyncio
async def test_perimetre_regional(db: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc:
        await atelier.proposer_ajout(db, BRC_AUTRE, LienPosteURCreate(poste_id=100, unite_releve="1100201P"))
    assert exc.value.status_code == 403
    page = await atelier.lister(db, BRC_AUTRE, poste_id=None, a_valider=False, recherche=None, page=1, page_size=50)
    assert page.total == 0
    assert [p.code for p in await atelier.rechercher_postes(db, BRC_AUTRE, "P")] == []
    assert [p.code for p in await atelier.rechercher_postes(db, BRC, "Poste")] == ["P100", "P101"]
    # SAQS : national, valide mais ne propose pas
    assert (await atelier.lister(db, SAQS, poste_id=None, a_valider=False, recherche=None, page=1, page_size=50)).total == 1
    with pytest.raises(HTTPException):
        await atelier.proposer_ajout(db, SAQS, LienPosteURCreate(poste_id=100, unite_releve="1100201P"))
    ur = await atelier.rechercher_ur(db, BRC, "11002")
    assert [(u.unite_releve, u.nb_contrats, u.nb_postes) for u in ur] == [("1100200I", 100, 1), ("1100201P", 30, 0)]
