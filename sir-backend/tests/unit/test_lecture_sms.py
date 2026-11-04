"""Lecture d'un SMS en texte libre → pré-remplissage de la saisie d'interruption."""

from datetime import datetime

from app.repositories.lecture_sms_repository import CauseRef, DepartRef
from app.services.lecture_sms_service import analyser

DEPARTS = [
    DepartRef(1, "F001", "HANN 2", 10, "HANN", 1),
    DepartRef(2, "F002", "BEL AIR", 11, "CAP DES BICHES", 1),
    DepartRef(3, "F003", "SOCOCIM", 12, "RUFISQUE", 1),
    DepartRef(4, "F004", "KAOLACK VILLE", 13, "KAOLACK", 2),
    DepartRef(5, "F005", "PORT", 14, "BEL AIR", 1),
    DepartRef(6, "F006", "PORT", 15, "KAOLACK", 2),
]
CAUSES = [CauseRef(1, "Défaut câble"), CauseRef(2, "Câble"), CauseRef(3, "Élagage")]
MAINTENANT = datetime(2026, 11, 4, 9, 45)


def lire(texte: str):
    return analyser(texte, DEPARTS, CAUSES, MAINTENANT)


def test_declenchement_complet() -> None:
    lecture = lire("Déclenchement départ Hann 2 à 08h15 suite défaut câble")
    assert lecture.evenement == "apparition"
    assert [d.id for d in lecture.departs] == [1]
    assert lecture.date_apparition == datetime(2026, 11, 4, 8, 15)
    assert lecture.cause is not None and lecture.cause.id == 1  # le libellé le plus long
    assert lecture.date_remise is None
    assert lecture.confiance >= 0.9


def test_remise_derniere_heure() -> None:
    lecture = lire("DEP BEL AIR remis sous tension a 9:30")
    assert lecture.evenement == "remise"
    assert [d.id for d in lecture.departs] == [2]
    assert lecture.date_remise == datetime(2026, 11, 4, 9, 30)


def test_apparition_et_remise_dans_le_meme_sms() -> None:
    lecture = lire("Decl Sococim 7h40, retabli 8h05")
    assert lecture.evenement == "apparition"
    assert lecture.date_apparition == datetime(2026, 11, 4, 7, 40)
    assert lecture.date_remise == datetime(2026, 11, 4, 8, 5)


def test_faute_de_frappe_et_date_explicite() -> None:
    lecture = lire("coupure dpt KAOLAK VILLE le 03/11 a 22h10")
    assert [d.id for d in lecture.departs] == [4]
    assert lecture.date_apparition == datetime(2026, 11, 3, 22, 10)


def test_heure_du_soir_envoyee_apres_minuit() -> None:
    lecture = analyser("Déclenchement Hann 2 23h50", DEPARTS, CAUSES, datetime(2026, 11, 5, 0, 20))
    assert lecture.date_apparition == datetime(2026, 11, 4, 23, 50)


def test_nom_homonyme_departage_par_le_poste_source() -> None:
    lecture = lire("Incident départ PORT poste Kaolack 6h")
    assert [d.id for d in lecture.departs] == [6]
    ambigu = lire("Incident départ PORT 6h")
    assert {d.id for d in ambigu.departs} == {5, 6}


def test_travaux_programmes() -> None:
    lecture = lire("Travaux programmés élagage départ Hann 2 de 9h à 13h")
    assert lecture.evenement == "apparition"
    assert lecture.is_programme
    assert lecture.cause is not None and lecture.cause.id == 3


def test_message_sans_interruption() -> None:
    lecture = lire("Réunion de coordination demain 10h salle B")
    assert lecture.evenement == "inconnu"
    assert lecture.confiance == 0.0


def test_h_suivi_d_un_nom_n_est_pas_une_heure() -> None:
    lecture = lire("Déclenchement 2 HANN 2")
    assert lecture.date_apparition is None


def test_requete_departs_sql_server() -> None:
    from sqlalchemy.dialects import mssql

    from app.repositories.lecture_sms_repository import requete_departs

    sql = str(requete_departs().compile(dialect=mssql.dialect()))
    assert "IS 1" not in sql
    assert "coalesce" in sql.lower()
