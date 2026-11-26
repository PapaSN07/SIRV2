"""Correspondances FIS administrées : modèle, repository, service (tests écrits avant le code).

Une correspondance rattache un libellé du fichier FIS (normalisé : minuscules, espaces de bord
retirés, espace insécable remplacé) à une entrée du Référentiel (nature, cause, siège,
signalisation). Elle est créée et supprimée par l'Admin SCR (droits du Référentiel
distribution), lue par l'import FIS avant la table interne.

Les modules testés n'existent pas encore : ils sont importés dans les fixtures et les tests,
pour que leur absence fasse échouer ces tests sans casser la collecte des autres fichiers.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, UniqueConstraint, event, func, select
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.models  # noqa: F401  (configuration des relations)
from app.models.referentiel import Cause, Nature, Siege, Signalisation
from app.models.utilisateurs import Utilisateur


def _modele() -> Any:
    return importlib.import_module("app.models.correspondance_fis").CorrespondanceFis


def _repo() -> Any:
    return importlib.import_module("app.repositories.correspondance_fis_repository")


def _svc() -> Any:
    return importlib.import_module("app.services.correspondance_fis_service")


def _schemas() -> Any:
    return importlib.import_module("app.schemas.correspondance_fis")


def _user(nom: str, id_: int = 1) -> SimpleNamespace:
    return SimpleNamespace(id=id_, login=nom.lower(), user_roles=[SimpleNamespace(role=SimpleNamespace(nom=nom))])


ADMIN_SCR = _user("ADMIN_SCR", 1)
SUPERADMIN = _user("SUPERADMIN", 2)
BCC = _user("BCC", 3)
ADMIN_DISPATCHING = _user("ADMIN_DISPATCHING", 4)
ADMIN_SAQS = _user("ADMIN_SAQS", 5)


# ---------------------------------------------------------------------------
# Base SQLite
# ---------------------------------------------------------------------------


@pytest.fixture
async def db() -> Any:
    CorrespondanceFis = _modele()
    moteur = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}})
    event.listen(
        moteur.sync_engine, "connect", lambda c, _: c.create_function("getdate", 0, lambda: "2026-11-26 08:00:00")
    )
    async with moteur.begin() as conn:
        for modele in (Utilisateur, Nature, Cause, Siege, Signalisation, CorrespondanceFis):
            await conn.run_sync(modele.__table__.create)
    async with AsyncSession(moteur, expire_on_commit=False) as session:
        session.add_all(
            [
                Nature(id=1, code="COUPURE", libelle="Coupure", is_active=True),
                Nature(id=2, code="ANCIENNE", libelle="Ancienne nature", is_active=False),
                Cause(id=1, code="FACT_EXO", libelle="Facteurs exogènes", type_reseau="distribution", is_active=True),
                Cause(id=2, code="MANOEUVRE", libelle="Manoeuvre", type_reseau="commun", is_active=True),
                Cause(id=3, code="TRAV_HTB", libelle="Travaux réseau HTB", type_reseau="transport", is_active=True),
                Cause(id=4, code="INCENDIE", libelle="Incendie", type_reseau="distribution", is_active=False),
                Siege(id=1, code="CABLE", libelle="Câble", type_reseau="distribution", is_active=True),
                Siege(id=2, code="DISJ", libelle="Disjoncteur", type_reseau="transport", is_active=True),
                Signalisation(id=1, code="DEF_TERRE", libelle="Défaut terre", type_reseau="distribution", is_active=True),
                Signalisation(id=2, code="BUCHHOLZ", libelle="Buchholz", type_reseau="transport", is_active=True),
            ]
        )
        await session.commit()
        yield session
    await moteur.dispose()


@pytest.fixture(autouse=True)
def _sans_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le journal d'audit n'est pas l'objet de ces tests (table absente de la base SQLite)."""
    import app.utils.audit as audit

    monkeypatch.setattr(audit, "log_audit", AsyncMock())
    try:
        module = _svc()
    except ModuleNotFoundError:
        return
    monkeypatch.setattr(module, "log_audit", AsyncMock(), raising=False)


def _body(categorie: str, libelle: str, referentiel_id: int, is_force_majeure: bool | None = None) -> Any:
    return _schemas().CorrespondanceFisCreate(
        categorie=categorie, libelle_fis=libelle, referentiel_id=referentiel_id, is_force_majeure=is_force_majeure
    )


async def _compter(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(_modele()))).scalar_one()


# ---------------------------------------------------------------------------
# Modèle
# ---------------------------------------------------------------------------


def test_modele_table_et_colonnes() -> None:
    table = _modele().__table__
    assert table.name == "correspondances_fis"
    colonnes = set(table.c.keys())
    attendues = {
        "id", "categorie", "libelle_fis", "nature_id", "cause_id", "siege_id", "signalisation_id",
        "is_force_majeure", "created_by_id", "created_at",
    }
    assert attendues <= colonnes
    assert table.c.categorie.type.length == 20
    assert table.c.libelle_fis.type.length == 200
    for nom in ("nature_id", "cause_id", "siege_id", "signalisation_id", "is_force_majeure"):
        assert table.c[nom].nullable, nom
    assert table.c.created_at.server_default is not None
    cibles = {fk.column.table.name for fk in table.foreign_keys}
    assert {"natures", "causes", "sieges", "signalisations", "utilisateurs"} <= cibles


def test_modele_unicite_et_controle_de_categorie() -> None:
    table = _modele().__table__
    uniques = [
        {c.name for c in contrainte.columns}
        for contrainte in table.constraints
        if isinstance(contrainte, UniqueConstraint)
    ] + [{c.name for c in index.columns} for index in table.indexes if index.unique]
    assert {"categorie", "libelle_fis"} in uniques
    checks = " ".join(str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint))
    for categorie in ("nature", "cause", "siege", "signalisation"):
        assert f"'{categorie}'" in checks


def test_modele_relations() -> None:
    relations = set(_modele().__mapper__.relationships.keys())
    assert {"nature", "cause", "siege", "signalisation"} <= relations


# ---------------------------------------------------------------------------
# Service : création (droits, validations, normalisation)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("user", [ADMIN_SCR, SUPERADMIN])
async def test_creation_par_admin_scr_ou_superadmin(db: AsyncSession, user: Any) -> None:
    reponse = await _svc().creer(db, user, _body("cause", "  Chute de\xa0MÉTÉORITE ", 1, True))
    assert reponse.id is not None
    assert reponse.categorie == "cause"
    assert reponse.libelle_fis == "chute de météorite"
    assert reponse.referentiel_id == 1
    assert reponse.referentiel_code == "FACT_EXO"
    assert reponse.referentiel_libelle == "Facteurs exogènes"
    assert reponse.is_force_majeure is True
    ligne = (await db.execute(select(_modele()))).scalars().one()
    assert (ligne.cause_id, ligne.nature_id, ligne.siege_id, ligne.signalisation_id) == (1, None, None, None)
    assert ligne.created_by_id == user.id


@pytest.mark.parametrize(
    ("categorie", "referentiel_id", "colonne"),
    [("nature", 1, "nature_id"), ("cause", 2, "cause_id"), ("siege", 1, "siege_id"), ("signalisation", 1, "signalisation_id")],
)
async def test_creation_renseigne_seulement_la_cle_de_la_categorie(
    db: AsyncSession, categorie: str, referentiel_id: int, colonne: str
) -> None:
    await _svc().creer(db, ADMIN_SCR, _body(categorie, "Libellé FIS", referentiel_id))
    ligne = (await db.execute(select(_modele()))).scalars().one()
    for nom in ("nature_id", "cause_id", "siege_id", "signalisation_id"):
        assert getattr(ligne, nom) == (referentiel_id if nom == colonne else None), nom
    assert ligne.is_force_majeure is None


@pytest.mark.parametrize(
    ("user", "categorie", "referentiel_id"),
    [
        (BCC, "cause", 1),
        (BCC, "nature", 1),
        (BCC, "signalisation", 1),
        (ADMIN_DISPATCHING, "cause", 1),
        (ADMIN_DISPATCHING, "siege", 1),
        (ADMIN_DISPATCHING, "signalisation", 1),
        (ADMIN_SAQS, "cause", 1),
        (ADMIN_SAQS, "nature", 1),
    ],
)
async def test_creation_refusee_hors_admin_scr(db: AsyncSession, user: Any, categorie: str, referentiel_id: int) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _svc().creer(db, user, _body(categorie, "Libellé FIS", referentiel_id))
    assert exc_info.value.status_code == 403
    assert await _compter(db) == 0


async def _attendre_422(db: AsyncSession, **champs: Any) -> None:
    """422 : refus du schéma Pydantic (→ 422 par FastAPI) ou du service."""
    try:
        body = _schemas().CorrespondanceFisCreate(**champs)
    except ValidationError:
        return
    with pytest.raises(HTTPException) as exc_info:
        await _svc().creer(db, ADMIN_SCR, body)
    assert exc_info.value.status_code == 422
    assert await _compter(db) == 0


@pytest.mark.parametrize(
    "champs",
    [
        {"categorie": "cause", "libelle_fis": "   ", "referentiel_id": 1},  # libellé vide
        {"categorie": "cause", "libelle_fis": "\xa0", "referentiel_id": 1},
        {"categorie": "feeder", "libelle_fis": "X", "referentiel_id": 1},  # catégorie inconnue
        {"categorie": "cause", "libelle_fis": "X", "referentiel_id": 999},  # cible inexistante
        {"categorie": "cause", "libelle_fis": "X", "referentiel_id": 3},  # cause transport
        {"categorie": "cause", "libelle_fis": "X", "referentiel_id": 4},  # cause inactive
        {"categorie": "nature", "libelle_fis": "X", "referentiel_id": 2},  # nature inactive
        {"categorie": "siege", "libelle_fis": "X", "referentiel_id": 2},  # siège transport
        {"categorie": "signalisation", "libelle_fis": "X", "referentiel_id": 2},  # signalisation transport
        {"categorie": "siege", "libelle_fis": "X", "referentiel_id": 1, "is_force_majeure": True},  # FM hors cause
        {"categorie": "nature", "libelle_fis": "X", "referentiel_id": 1, "is_force_majeure": False},
    ],
)
async def test_creation_invalide_422(db: AsyncSession, champs: dict[str, Any]) -> None:
    await _attendre_422(db, **champs)


async def test_doublon_categorie_libelle_normalise_409(db: AsyncSession) -> None:
    await _svc().creer(db, ADMIN_SCR, _body("cause", "Chute de météorite", 1))
    with pytest.raises(HTTPException) as exc_info:
        await _svc().creer(db, ADMIN_SCR, _body("cause", "  CHUTE DE MÉTÉORITE ", 2))
    assert exc_info.value.status_code == 409
    assert await _compter(db) == 1


async def test_meme_libelle_autre_categorie_accepte(db: AsyncSession) -> None:
    await _svc().creer(db, ADMIN_SCR, _body("cause", "Défaut terre", 1))
    await _svc().creer(db, ADMIN_SCR, _body("signalisation", "Défaut terre", 1))
    assert await _compter(db) == 2


# ---------------------------------------------------------------------------
# Service : liste et suppression
# ---------------------------------------------------------------------------


async def _jeu(db: AsyncSession) -> None:
    await _svc().creer(db, ADMIN_SCR, _body("cause", "Chute de météorite", 1, True))
    await _svc().creer(db, ADMIN_SCR, _body("siege", "Boîte de jonction", 1))
    await _svc().creer(db, ADMIN_SCR, _body("nature", "Coupure pour travaux", 1))


async def test_lister_tout_et_par_categorie(db: AsyncSession) -> None:
    await _jeu(db)
    tout = await _svc().lister(db)
    assert {(c.categorie, c.libelle_fis) for c in tout} == {
        ("cause", "chute de météorite"),
        ("siege", "boîte de jonction"),
        ("nature", "coupure pour travaux"),
    }
    causes = await _svc().lister(db, categorie="cause")
    assert [(c.categorie, c.referentiel_code, c.is_force_majeure) for c in causes] == [("cause", "FACT_EXO", True)]
    assert causes[0].created_at is not None


async def test_supprimer_par_admin_scr(db: AsyncSession) -> None:
    await _jeu(db)
    cible = (await _svc().lister(db, categorie="siege"))[0]
    await _svc().supprimer(db, ADMIN_SCR, cible.id)
    assert {c.categorie for c in await _svc().lister(db)} == {"cause", "nature"}


@pytest.mark.parametrize("user", [BCC, ADMIN_DISPATCHING, ADMIN_SAQS])
async def test_supprimer_refuse_hors_admin_scr(db: AsyncSession, user: Any) -> None:
    await _jeu(db)
    cible = (await _svc().lister(db, categorie="cause"))[0]
    with pytest.raises(HTTPException) as exc_info:
        await _svc().supprimer(db, user, cible.id)
    assert exc_info.value.status_code == 403
    assert await _compter(db) == 3


async def test_supprimer_inconnue_404(db: AsyncSession) -> None:
    with pytest.raises(HTTPException) as exc_info:
        await _svc().supprimer(db, ADMIN_SCR, 999)
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Repository : dictionnaire lu par l'import FIS
# ---------------------------------------------------------------------------


async def test_dictionnaire_clefs_normalisees_et_cibles_chargees(db: AsyncSession) -> None:
    await _jeu(db)
    db.expunge_all()  # les cibles doivent être chargées par la requête (pas de chargement paresseux en async)
    dico = await _repo().dictionnaire(db)
    assert set(dico) == {
        ("cause", "chute de météorite"),
        ("siege", "boîte de jonction"),
        ("nature", "coupure pour travaux"),
    }
    cause = dico[("cause", "chute de météorite")]
    assert cause.cause.code == "FACT_EXO"
    assert cause.is_force_majeure is True
    assert dico[("siege", "boîte de jonction")].siege.code == "CABLE"
    assert dico[("nature", "coupure pour travaux")].nature.code == "COUPURE"


async def test_dictionnaire_vide(db: AsyncSession) -> None:
    assert await _repo().dictionnaire(db) == {}


# ---------------------------------------------------------------------------
# Requêtes compilées SQL Server
# ---------------------------------------------------------------------------


def _db_capture() -> tuple[MagicMock, list[Any]]:
    requetes: list[Any] = []
    resultat = MagicMock()
    resultat.scalars.return_value.all.return_value = []
    resultat.scalars.return_value.unique.return_value.all.return_value = []
    resultat.unique.return_value.scalars.return_value.all.return_value = []
    resultat.all.return_value = []

    async def _execute(requete: Any, *args: Any, **kwargs: Any) -> Any:
        requetes.append(requete)
        return resultat

    async def _scalars(requete: Any, *args: Any, **kwargs: Any) -> Any:
        requetes.append(requete)
        return resultat.scalars.return_value

    resultat.scalars.return_value.__iter__ = lambda self: iter([])
    db = MagicMock()
    db.execute = AsyncMock(side_effect=_execute)
    db.scalars = AsyncMock(side_effect=_scalars)
    return db, requetes


@pytest.mark.parametrize(
    "appel",
    [
        lambda repo, db: repo.dictionnaire(db),
        lambda repo, db: repo.lister(db),
        lambda repo, db: repo.lister(db, categorie="cause"),
    ],
)
async def test_requetes_repository_compilees_sql_server(appel: Any) -> None:
    db, requetes = _db_capture()
    await appel(_repo(), db)
    assert requetes, "aucune requête émise"
    for requete in requetes:
        sql = str(requete.compile(dialect=mssql.dialect()))
        assert "correspondances_fis" in sql
        assert "IS 1" not in sql and "IS 0" not in sql, sql
        assert "SELECT *" not in sql
