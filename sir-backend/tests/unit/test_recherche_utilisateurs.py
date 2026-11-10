"""Recherche d'un compte par login, matricule, nom, prénom ou e-mail (administration)."""

from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session

from app.models.utilisateurs import Utilisateur
from app.repositories.admin_utilisateur_repository import filtre_recherche


def _base() -> Session:
    moteur = create_engine("sqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(moteur, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-10 00:00:00"))
    Utilisateur.__table__.create(moteur)
    session = Session(moteur)
    session.add_all([
        Utilisateur(id=1, login="adiop", password_hash="x", nom="DIOP", prenom="Awa", email="awa.diop@senelec.sn", matricule="604512"),
        Utilisateur(id=2, login="msene", password_hash="x", nom="Sène", prenom="Mamadou", email="m.sene@senelec.sn", matricule="611020"),
        Utilisateur(id=3, login="bcc_50", password_hash="x", nom="Fall", prenom="Ibrahima", email=None, matricule=None),
    ])
    session.commit()
    return session


def _ids(session: Session, texte: str) -> list[int]:
    filtre = filtre_recherche(texte)
    requete = select(Utilisateur.id).order_by(Utilisateur.id)
    if filtre is not None:
        requete = requete.where(filtre)
    return list(session.scalars(requete))


def test_recherche_par_champ() -> None:
    s = _base()
    assert _ids(s, "6045") == [1]  # matricule
    assert _ids(s, "diop") == [1]  # nom, sans tenir compte de la casse
    assert _ids(s, "M.SENE@") == [2]  # e-mail
    assert _ids(s, "bcc_") == [3]  # login, « _ » pris à la lettre
    assert _ids(s, "awa diop") == [1]  # prénom + nom, dans n'importe quel ordre
    assert _ids(s, "ibrahima diop") == []
    assert _ids(s, "  ") == [1, 2, 3]
    assert _ids(s, "%") == []


def test_recherche_sql_server() -> None:
    sql = str(select(Utilisateur.id).where(filtre_recherche("diop")).compile(dialect=mssql.dialect()))
    assert "utilisateurs.matricule) LIKE" in sql and "ESCAPE" in sql
