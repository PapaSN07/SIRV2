"""Reprise du répertoire SMS SIR v1 : dédoublonnage par numéro, groupes, colonnes accentuées."""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
# sir-backend/scripts porte le même nom de paquet : forcer celui de la racine du dépôt
if "scripts" in sys.modules and not hasattr(sys.modules["scripts"], "migration"):
    for nom in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[nom]

from scripts.migration.import_repertoire_sms import champ, construire, ecrire, normaliser_numero  # noqa: E402


def test_champ_accents_et_casse() -> None:
    assert champ({"PRÉNOMNOM": "  Awa   DIOP "}, "prénomnom") == "Awa DIOP"
    assert champ({"prenomnom": "Awa"}, "prénomnom") == "Awa"
    assert champ({"Telephone": None}, "Telephone") == ""


def _sources():
    groupes = [{"Groupe": "DR DAKAR", "exploitation": "BCC"}, {"Groupe": "DIRECTION", "exploitation": "dispatching"}]
    destinataires = [
        {"prénomnom": "Awa DIOP", "Telephone": "77 740 82 54", "Fonctiondes": "Chef BCC", "Groupe": "DR DAKAR", "Matricule": "4051"},
        {"prénomnom": "Awa DIOP bis", "Telephone": "+221777408254", "Fonctiondes": "", "Groupe": "DIRECTION"},
        {"prénomnom": "Sans numéro", "Telephone": "", "Groupe": "DR DAKAR"},
        {"prénomnom": "Moussa FALL", "Telephone": "781451126", "Groupe": "NOUVEAU", "exploitation": "BRC"},
    ]
    repertoire = [
        {"Prénom": "Awa", "Nom": "DIOP", "Telephone": "777408254", "fonctionagent": "Ingénieur"},
        {"Prénom": "Ibou", "Nom": "NDIAYE", "Telephone": "00221 76 000 00 01", "fonctionagent": "Technicien", "Matricule": "0"},
    ]
    return groupes, destinataires, repertoire


def test_construire_plusieurs_groupes_par_personne() -> None:
    groupes, contacts, rejets = construire(*_sources())

    assert groupes == {"DIRECTION": "DISPATCHING", "DR DAKAR": "BCC", "NOUVEAU": "BRC"}
    assert set(contacts) == {"777408254", "781451126", "760000001"}
    awa = contacts["777408254"]
    assert (awa.nom, awa.fonction, awa.groupes, awa.matricule) == ("Awa DIOP", "Chef BCC", {"DR DAKAR", "DIRECTION"}, 4051)
    ibou = contacts["760000001"]
    assert ibou.nom == "Ibou NDIAYE" and ibou.groupes == set() and ibou.matricule is None
    assert rejets["destinataire sans numéro valide"] == 1
    assert rejets["ligne supplémentaire (même numéro, autre groupe)"] == 1


def test_ecrire_fusionne_les_doublons_et_relie_les_groupes() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("ATTACH DATABASE ':memory:' AS dbo")
        c.exec_driver_sql("CREATE TABLE dbo.groupes_envoi (id INTEGER PRIMARY KEY, libelle TEXT UNIQUE, is_active INT, exploitation TEXT)")
        c.exec_driver_sql(
            "CREATE TABLE dbo.destinataires (id INTEGER PRIMARY KEY, nom TEXT, telephone TEXT, email TEXT, "
            "utilisateur_id INT, service_id INT, is_active INT, fonction TEXT, matricule INT)"
        )
        c.exec_driver_sql("CREATE TABLE dbo.destinataire_groupes (destinataire_id INT, groupe_id INT)")
        c.exec_driver_sql("CREATE TABLE dbo.sms_envoyes (id INTEGER PRIMARY KEY, destinataire_id INT)")
        c.exec_driver_sql("CREATE TABLE dbo.emails_envoyes (id INTEGER PRIMARY KEY, destinataire_id INT)")
        c.exec_driver_sql("INSERT INTO dbo.groupes_envoi VALUES (1, 'DR DAKAR', 1, NULL)")
        # reprise ETL : Awa sur deux lignes (une par groupe), la seconde avec un service et un SMS
        c.exec_driver_sql(
            "INSERT INTO dbo.destinataires VALUES (10, 'AWA DIOP', '777408254', NULL, NULL, NULL, 1, NULL, NULL),"
            "(11, 'AWA DIOP', '+221 77 740 82 54', 'awa@senelec.sn', NULL, 3, 1, NULL, NULL)"
        )
        c.exec_driver_sql("INSERT INTO dbo.sms_envoyes VALUES (1, 11)")
    with Session(engine) as session:
        session.connection().exec_driver_sql("SELECT 1")
        groupes, contacts, _ = construire(*_sources())
        bilan = ecrire(session, groupes, contacts)
        q = lambda sql: session.execute(text(sql)).all()  # noqa: E731
        assert bilan["doublons_fusionnes"] == 1 and bilan["destinataires_crees"] == 2 and bilan["groupes_crees"] == 2
        assert q("SELECT id, email, service_id, fonction, matricule FROM dbo.destinataires WHERE telephone = '777408254'") == [
            (10, "awa@senelec.sn", 3, "Chef BCC", 4051)
        ]
        assert q("SELECT destinataire_id FROM dbo.sms_envoyes") == [(10,)]
        assert q(
            "SELECT g.libelle FROM dbo.destinataire_groupes x JOIN dbo.groupes_envoi g ON g.id = x.groupe_id "
            "WHERE x.destinataire_id = 10 ORDER BY g.libelle"
        ) == [("DIRECTION",), ("DR DAKAR",)]
        assert q("SELECT exploitation FROM dbo.groupes_envoi WHERE libelle = 'DR DAKAR'") == [("BCC",)]
        # relancer ne crée rien de plus
        assert ecrire(session, groupes, contacts).get("destinataires_crees", 0) == 0


def test_normaliser_numero_identique_a_l_envoi() -> None:
    from app.services.sms_gateway import normaliser_numero as envoi

    for n in ("+221 77 740 82 54", "00221777408254", "77-740-82-54", "221777408254"):
        assert normaliser_numero(n) == envoi(n)
