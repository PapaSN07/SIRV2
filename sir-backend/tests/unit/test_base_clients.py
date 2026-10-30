"""Base clients SAIFI/SAIDI : lecture du fichier H2MC, import, clients par poste et par service."""

from datetime import datetime

import pytest
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.services import base_clients_service as svc


def test_normaliser_et_preparer() -> None:
    brutes = [
        {"unite_releve": " 1100200i ", "nb_contrats": 130, "code_agence": "110", "delegation": "DC1"},
        {"unite_releve": "1100200I", "nb_contrats": "7"},  # doublon additionné
        {"unite_releve": "1400595W", "nb_contrats": 1},  # agence déduite du code UR
        {"unite_releve": "", "nb_contrats": 3},
        {"unite_releve": "5420002P", "nb_contrats": "abc"},
    ]
    lignes, rejets = svc.preparer_lignes(2026, 10, brutes, {"110": 1}, svc.SOURCE_BI)
    assert rejets == 2
    par_ur = {lg["unite_releve"]: lg for lg in lignes}
    assert par_ur["1100200I"]["nb_contrats"] == 137 and par_ur["1100200I"]["agence_id"] == 1
    assert par_ur["1400595W"]["code_agence"] == "140" and par_ur["1400595W"]["agence_id"] is None


def test_lire_fichier_h2mc(tmp_path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["Delegation (code)", "Delegation (Des. Courte)", "Agence", "Agence (code)", "Unite de Releve",
               "Unite Releve (Code)", "Nombre de contrat"])
    ws.append(["100", "DC1", "Bourguiba", "110", "Bourguiba Bord 0200 CG impair", "1100200I", 131])
    ws.append([None, None, None, None, "Patte d'Oi Bord 0595 WOYOFAL", "1400595W", 1])
    chemin = tmp_path / "nombredeclientsh2mc_102026.xlsx"
    wb.save(chemin)
    brutes = svc.lire_fichier(chemin)
    assert brutes[0]["unite_releve"] == "1100200I" and brutes[0]["nb_contrats"] == 131
    assert brutes[0]["code_agence"] == "110" and brutes[1]["code_agence"] is None


def test_lire_fichier_sans_colonnes(tmp_path) -> None:
    wb = Workbook()
    wb.active.append(["A", "B"])
    chemin = tmp_path / "x.xlsx"
    wb.save(chemin)
    with pytest.raises(svc.BaseClientsErreur):
        svc.lire_fichier(chemin)


@pytest.mark.asyncio
async def test_importer_recalcule_postes_et_services() -> None:
    # schéma dbo absent sous SQLite ; l'import valide (commit) puis relit sur une autre connexion
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    async with engine.begin() as c:
        for ddl in (
            "CREATE TABLE agences (id INTEGER PRIMARY KEY, code TEXT)",
            "CREATE TABLE services (id INTEGER PRIMARY KEY, agence_id INT)",
            "CREATE TABLE postes (id INTEGER PRIMARY KEY, nombre_clients INT)",
            "CREATE TABLE nombre_client_mois (id INTEGER PRIMARY KEY, service_id INT, annee INT, mois INT, "
            "nombre_clients INT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
            "CREATE TABLE contrats_unites_releve (id INTEGER PRIMARY KEY, annee INT, mois INT, unite_releve TEXT, "
            "libelle TEXT, code_agence TEXT, delegation TEXT, agence_id INT, nb_contrats INT, date_maj DATETIME, source TEXT)",
            "CREATE TABLE postes_unites_releve (id INTEGER PRIMARY KEY, poste_id INT, unite_releve TEXT, statut TEXT, "
            "modifie_par_id INT, modifie_le DATETIME, valide_par_id INT, valide_le DATETIME)",
            "INSERT INTO agences VALUES (1, 'AG110'), (2, 'AG140')",
            "INSERT INTO services VALUES (5, 1), (6, 1), (7, 2)",
            "INSERT INTO postes VALUES (100, 999), (101, NULL), (102, 50)",
            "INSERT INTO nombre_client_mois (service_id, annee, mois, nombre_clients) VALUES (5, 2026, 10, 1)",
            # A partagée entre 100 et 101 ; B seulement 100 ; C proposée (ne compte pas encore)
            "INSERT INTO postes_unites_releve (poste_id, unite_releve, statut) VALUES "
            "(100, '1100200I', 'valide'), (101, '1100200I', 'valide'), (100, '1100201P', 'suppression_proposee'),"
            "(102, '1400595W', 'ajout_propose')",
        ):
            await c.exec_driver_sql(ddl)
    brutes = [
        {"unite_releve": "1100200I", "nb_contrats": 100, "code_agence": "110", "date_maj": datetime(2026, 10, 30, 5, 30)},
        {"unite_releve": "1100201P", "nb_contrats": 10, "code_agence": "110"},
        {"unite_releve": "1400595W", "nb_contrats": 40},
        {"unite_releve": "9990001W", "nb_contrats": 5},  # agence inconnue
    ]
    try:
        async with AsyncSession(engine) as db:
            bilan = await svc.importer(db, 2026, 10, brutes, svc.SOURCE_BI)
            postes = dict((await db.execute(text("SELECT id, nombre_clients FROM postes"))).all())
            ncm = (
                await db.execute(text("SELECT service_id, nombre_clients FROM nombre_client_mois ORDER BY service_id"))
            ).all()
            resume = await svc.resume(db)
    finally:
        await engine.dispose()

    assert (bilan.unites_releve, bilan.contrats, bilan.contrats_sans_agence) == (4, 155, 5)
    # poste 100 : moitié de A (50) + B (10) ; poste 101 : moitié de A ; poste 102 inchangé (lien non validé)
    assert postes == {100: 60, 101: 50, 102: 50}
    # agence 1 → service 5 (le premier), agence 2 → service 7 ; l'ancienne valeur du mois est remplacée
    assert ncm == [(5, 110), (7, 40)]
    p = resume["periodes"][0]
    assert (p["annee"], p["mois"], p["ur"], p["contrats"], p["ur_rattachees"], p["contrats_rattaches"]) == (
        2026, 10, 4, 155, 2, 110
    )
    assert resume["liens"] == {"ajout_propose": 1, "suppression_proposee": 1, "valide": 2}
