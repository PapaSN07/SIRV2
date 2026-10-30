"""Reprise de l'historique smsenvoye (SIR v1) : statuts, rattachements, pas de doublon."""

import sys
from datetime import datetime
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2].parent
if str(_REPO) in sys.path:
    sys.path.remove(str(_REPO))
sys.path.insert(0, str(_REPO))
if "scripts" in sys.modules and not hasattr(sys.modules["scripts"], "migration"):
    for nom in [m for m in sys.modules if m == "scripts" or m.startswith("scripts.")]:
        del sys.modules[nom]

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from scripts.migration.import_sms_historique import ecrire, preparer  # noqa: E402

LIGNES = [
    {"dateEnvoi": "2025-03-01T08:15:00", "Telephone": "77 740 82 54", "messageenvoye": "Coupure HANN ( from BCC )",
     "NInterruption": "26104", "Login": "4051", "Status_Code": "200", "Status_Text": "Message envoye", "messageID": "316"},
    {"dateEnvoi": "2025-03-01T08:15:00", "Telephone": "781451126", "destinataire": "Moussa FALL",
     "messageenvoye": "Coupure HANN ( from BCC )", "NInterruption": "0", "Login": "4051", "Status_Code": "0",
     "Status_Text": "PAS DE REPONSE"},
    {"dateEnvoi": "", "Telephone": "781451126", "messageenvoye": "x"},
    {"dateEnvoi": "2019-01-01T00:00:00", "Telephone": "781451126", "messageenvoye": "ancien", "Status_Code": "200"},
]


def test_preparer_statuts_et_filtre_annee() -> None:
    sms, rejets = preparer(LIGNES, depuis=2020)
    assert [(s["numero"], s["statut"], s["code"], s["erreur"]) for s in sms] == [
        ("777408254", "envoye", "200", None),
        ("781451126", "echec", "0", "PAS DE REPONSE"),
    ]
    assert sms[0]["date"] == datetime(2025, 3, 1, 8, 15) and rejets["sans date d'envoi"] == 1


def test_ecrire_rattache_et_ne_double_pas() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("ATTACH DATABASE ':memory:' AS dbo")
        c.exec_driver_sql(
            "CREATE TABLE dbo.destinataires (id INTEGER PRIMARY KEY, nom TEXT, telephone TEXT, email TEXT, "
            "utilisateur_id INT, service_id INT, is_active INT)"
        )
        c.exec_driver_sql("CREATE TABLE dbo.interruptions (id INTEGER PRIMARY KEY, numero_interruption INT)")
        c.exec_driver_sql("CREATE TABLE dbo.utilisateurs (id INTEGER PRIMARY KEY, login TEXT)")
        c.exec_driver_sql(
            "CREATE TABLE dbo.sms_envoyes (id INTEGER PRIMARY KEY, destinataire_id INT, entity_type TEXT, entity_id INT, "
            "contenu TEXT, statut TEXT, sent_at DATETIME, erreur TEXT, created_at DATETIME, envoye_par_id INT, "
            "code_retour TEXT, message_id TEXT)"
        )
        c.exec_driver_sql("INSERT INTO dbo.destinataires VALUES (10, 'Awa DIOP', '+221777408254', NULL, NULL, NULL, 1)")
        c.exec_driver_sql("INSERT INTO dbo.interruptions VALUES (500, 26104)")
        c.exec_driver_sql("INSERT INTO dbo.utilisateurs VALUES (7, 'awa.diop')")
    sms, _ = preparer(LIGNES, depuis=2020)
    with Session(engine) as session:
        bilan = ecrire(session, sms, {"4051": "AWA.DIOP"})
        lignes = session.execute(
            text("SELECT destinataire_id, entity_type, entity_id, statut, envoye_par_id, code_retour, message_id FROM dbo.sms_envoyes ORDER BY id")
        ).all()
        assert lignes == [(10, "interruption", 500, "envoye", 7, "200", "316"), (11, "manual", None, "echec", 7, "0", None)]
        assert session.execute(text("SELECT nom, is_active FROM dbo.destinataires WHERE id = 11")).one() == ("Moussa FALL", 0)
        assert bilan["destinataires_inactifs_crees"] == 1
        assert ecrire(session, sms, {}).get("deja_repris") == 2
