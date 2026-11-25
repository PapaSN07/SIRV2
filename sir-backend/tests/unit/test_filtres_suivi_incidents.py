"""Filtres communs des onglets « Suivi incidents » (étape 2 : fondations).

- B. Schéma ``app.schemas.suivi_incidents.FiltresIncidents`` (validation Pydantic v2).
- C. ``app.repositories.suivi_incidents_repository.appliquer_filtres`` : conditions SQL sur une
  requête qui part de ``Interruption`` (SQL Server compilé + comportement réel sur SQLite).
- D. Colonne ``causes.est_exogene`` (``Cause.est_exogene``).

Écrits avant le code (circuit « tests avant le code »).
"""

import re
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import Boolean, select
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

DEBUT = date(2026, 11, 14)
FIN = date(2026, 11, 20)


def _filtres(**kwargs: object):
    from app.schemas.suivi_incidents import FiltresIncidents

    valeurs: dict[str, object] = {"debut": DEBUT, "fin": FIN}
    valeurs.update(kwargs)
    return FiltresIncidents(**valeurs)


# --------------------------------------------------------------------------------------------
# B. FiltresIncidents
# --------------------------------------------------------------------------------------------


def test_filtres_valeurs_par_defaut() -> None:
    """Seules les dates sont obligatoires ; les autres filtres valent None."""
    f = _filtres()
    assert (f.debut, f.fin) == (DEBUT, FIN)
    for champ in (
        "region_id", "service_id", "poste_source_id", "feeder_id", "nature_id", "cause_id",
        "reseau", "exogene",
    ):
        assert getattr(f, champ) is None, champ


def test_filtres_complets_acceptes() -> None:
    """Tous les champs renseignés ; les chaînes de requête sont converties (date, int, bool)."""
    from app.schemas.suivi_incidents import FiltresIncidents

    f = FiltresIncidents.model_validate(
        {
            "debut": "2026-11-01", "fin": "2026-11-25", "region_id": "1", "service_id": 2,
            "poste_source_id": 3, "feeder_id": 4, "nature_id": 5, "cause_id": 6,
            "reseau": "htb", "exogene": "false",
        }
    )
    assert f.debut == date(2026, 11, 1) and f.fin == date(2026, 11, 25)
    assert (f.region_id, f.service_id, f.poste_source_id, f.feeder_id, f.nature_id, f.cause_id) == (
        1, 2, 3, 4, 5, 6,
    )
    assert f.reseau == "htb"
    assert f.exogene is False


@pytest.mark.parametrize("champ", ["debut", "fin"])
def test_filtres_dates_obligatoires(champ: str) -> None:
    """debut et fin sont requis dans le schéma (la valeur par défaut est posée par le service)."""
    from app.schemas.suivi_incidents import FiltresIncidents

    valeurs = {"debut": DEBUT, "fin": FIN}
    del valeurs[champ]
    with pytest.raises(ValidationError):
        FiltresIncidents(**valeurs)


def test_filtres_un_seul_jour_accepte() -> None:
    """fin == debut : une journée, valide (fin incluse)."""
    f = _filtres(debut=FIN, fin=FIN)
    assert f.debut == f.fin == FIN


def test_filtres_fin_avant_debut_refusee() -> None:
    """fin < debut → ValidationError."""
    with pytest.raises(ValidationError):
        _filtres(debut=FIN, fin=DEBUT)


def test_filtres_plage_de_trois_ans_acceptee() -> None:
    """1 096 jours inclus (3 ans avec un 29 février) : accepté."""
    debut = date(2024, 1, 1)
    f = _filtres(debut=debut, fin=debut + timedelta(days=1095))
    assert (f.fin - f.debut).days == 1095


def test_filtres_plage_de_plus_de_trois_ans_refusee() -> None:
    """Nettement plus de 1 096 jours → ValidationError (protège la base)."""
    debut = date(2022, 1, 1)
    with pytest.raises(ValidationError):
        _filtres(debut=debut, fin=debut + timedelta(days=1097))
    with pytest.raises(ValidationError):
        _filtres(debut=date(2020, 1, 1), fin=date(2026, 11, 25))


@pytest.mark.parametrize(
    "champ", ["region_id", "service_id", "poste_source_id", "feeder_id", "nature_id", "cause_id"]
)
@pytest.mark.parametrize("valeur", [0, -3])
def test_filtres_identifiants_strictement_positifs(champ: str, valeur: int) -> None:
    """Un identifiant ≤ 0 → ValidationError."""
    with pytest.raises(ValidationError):
        _filtres(**{champ: valeur})


@pytest.mark.parametrize("reseau", ["bt", "HTX", "", "transport"])
def test_filtres_reseau_hta_ou_htb_seulement(reseau: str) -> None:
    """reseau ∈ {hta, htb} ou absent."""
    with pytest.raises(ValidationError):
        _filtres(reseau=reseau)


# --------------------------------------------------------------------------------------------
# D. Cause.est_exogene
# --------------------------------------------------------------------------------------------


def test_cause_est_exogene_colonne() -> None:
    """Booléen non nul, défaut faux côté Python et côté serveur (0)."""
    from app.models.referentiel import Cause

    assert hasattr(Cause, "est_exogene")
    colonne = Cause.__table__.c.est_exogene
    assert isinstance(colonne.type, Boolean)
    assert colonne.nullable is False
    assert colonne.server_default is not None
    assert str(colonne.server_default.arg).strip("'() ") in ("0", "false", "False")
    assert colonne.default is not None and colonne.default.arg is False


# --------------------------------------------------------------------------------------------
# C. appliquer_filtres — SQL Server compilé
# --------------------------------------------------------------------------------------------


def _sql(**kwargs: object) -> str:
    from app.models.interruptions import Interruption
    from app.repositories.suivi_incidents_repository import appliquer_filtres

    requete = appliquer_filtres(select(Interruption.id), _filtres(**kwargs))
    return str(requete.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))


def _nb_jointures_causes(sql: str) -> int:
    return len(re.findall(r"JOIN\s+(?:dbo\.)?causes\b", sql, re.IGNORECASE))


def test_sql_sans_filtre_facultatif() -> None:
    """Distribution, période fin incluse (< fin + 1 jour), aucune jointure sur causes."""
    sql = _sql()
    assert re.search(r"type_direction = N?'distribution'", sql)
    assert "date_apparition >=" in sql and "date_apparition <" in sql
    assert "date_apparition <=" not in sql
    assert "2026-11-14" in sql
    assert "2026-11-21" in sql  # lendemain de la fin, borne exclue
    assert "2026-11-20" not in sql
    assert "causes" not in sql.lower().replace("cause_id", "")
    assert "IS 1" not in sql and "IS 0" not in sql


@pytest.mark.parametrize(
    ("champ", "colonne"),
    [
        ("region_id", "region_id"),
        ("service_id", "service_id"),
        ("poste_source_id", "poste_source_id"),
        ("feeder_id", "feeder_id"),
        ("nature_id", "nature_id"),
        ("cause_id", "cause_id"),
    ],
)
def test_sql_egalite_sur_les_identifiants(champ: str, colonne: str) -> None:
    """Chaque identifiant renseigné ajoute une égalité ; absent, aucune condition sur la colonne."""
    assert f"interruptions.{colonne} = 7" in _sql(**{champ: 7})
    assert f"interruptions.{colonne} =" not in _sql()


def test_sql_reseau_htb_reprend_condition_reseau() -> None:
    """reseau='htb' : jointure EXTERNE sur causes, libellés HTB / PRODUCTION / BLACK START."""
    sql = _sql(reseau="htb")
    haut = sql.upper()
    assert "LEFT OUTER JOIN" in haut
    assert _nb_jointures_causes(sql) == 1
    for motif in ("'%HTB%'", "'%PRODUCTION%'", "'%BLACK START%'"):
        assert motif in haut, motif
    assert "IS 1" not in sql


def test_sql_reseau_hta_garde_les_sans_cause() -> None:
    """reseau='hta' : négation du filtre HTB et interruptions sans cause conservées."""
    sql = _sql(reseau="hta")
    haut = sql.upper()
    assert "LEFT OUTER JOIN" in haut and _nb_jointures_causes(sql) == 1
    assert "NOT" in haut and "IS NULL" in haut


def test_sql_exogene_vrai_sans_is_1() -> None:
    """exogene=True → causes.est_exogene = 1 (jamais « IS 1 », refusé par SQL Server)."""
    sql = _sql(exogene=True)
    assert "LEFT OUTER JOIN" in sql.upper() and _nb_jointures_causes(sql) == 1
    assert "causes.est_exogene = 1" in sql
    assert "IS 1" not in sql


def test_sql_exogene_faux_garde_les_sans_cause() -> None:
    """exogene=False → est_exogene = 0 OU pas de cause (jointure externe)."""
    sql = _sql(exogene=False)
    assert "LEFT OUTER JOIN" in sql.upper() and _nb_jointures_causes(sql) == 1
    assert "causes.est_exogene = 0" in sql
    assert "IS NULL" in sql.upper()
    assert "IS 0" not in sql


def test_sql_reseau_et_exogene_une_seule_jointure() -> None:
    """reseau + exogene : la jointure sur causes n'est ajoutée qu'une fois."""
    sql = _sql(reseau="htb", exogene=True, cause_id=3)
    assert _nb_jointures_causes(sql) == 1
    assert "causes.est_exogene = 1" in sql
    assert "interruptions.cause_id = 3" in sql


def test_sql_cause_id_seul_sans_jointure() -> None:
    """Filtrer sur cause_id ne nécessite pas de jointure sur causes."""
    assert _nb_jointures_causes(_sql(cause_id=3)) == 0


# --------------------------------------------------------------------------------------------
# C. appliquer_filtres — comportement réel (SQLite en mémoire)
# --------------------------------------------------------------------------------------------


@pytest.fixture
async def db_sqlite():
    engine = create_async_engine(
        "sqlite+aiosqlite://", execution_options={"schema_translate_map": {"dbo": None}}
    )
    async with engine.begin() as c:
        for ddl in (
            "CREATE TABLE causes (id INTEGER PRIMARY KEY, code TEXT, libelle TEXT, type_reseau TEXT, "
            "is_active INT, est_exogene INT NOT NULL DEFAULT 0)",
            "CREATE TABLE interruptions (id INTEGER PRIMARY KEY, type_direction TEXT, "
            "date_apparition DATETIME, region_id INT, service_id INT, poste_source_id INT, "
            "feeder_id INT, nature_id INT, cause_id INT)",
            "INSERT INTO causes VALUES "
            "(1, 'C1', 'Défaut réseau HTB', 'distribution', 1, 0), "
            "(2, 'C2', 'Câble HTA', 'distribution', 1, 0), "
            "(3, 'C3', 'Arbre sur ligne', 'distribution', 1, 1), "
            "(4, 'C4', 'MANQUE PRODUCTION', 'distribution', 1, 1)",
            # id, direction, apparition, région, service, poste source, feeder, nature, cause
            "INSERT INTO interruptions VALUES "
            "(10, 'distribution', '2026-11-14 00:00:00.000000', 1, 1, 1, 1, 1, 1), "
            "(11, 'distribution', '2026-11-20 23:59:00.000000', 1, 1, 1, 2, 2, 2), "
            "(12, 'distribution', '2026-11-17 10:00:00.000000', 2, 2, 2, 3, 1, 3), "
            "(13, 'distribution', '2026-11-18 10:00:00.000000', 2, 2, 2, 3, 2, NULL), "
            "(14, 'distribution', '2026-11-19 10:00:00.000000', 1, 1, 1, 1, 1, 4), "
            # exclues : transport, OMVG, avant le début, après la fin
            "(20, 'transport', '2026-11-17 10:00:00.000000', 1, 1, 1, 1, 1, 1), "
            "(21, 'omvg', '2026-11-17 10:00:00.000000', 1, 1, 1, 1, 1, 1), "
            "(22, 'distribution', '2026-11-13 23:59:59.000000', 1, 1, 1, 1, 1, 1), "
            "(23, 'distribution', '2026-11-21 00:00:00.000000', 1, 1, 1, 1, 1, 1)",
        ):
            await c.exec_driver_sql(ddl)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filtres", "attendus"),
    [
        ({}, {10, 11, 12, 13, 14}),  # période bornes incluses, transport / OMVG exclus
        ({"debut": date(2026, 11, 20), "fin": date(2026, 11, 20)}, {11}),
        ({"debut": date(2026, 11, 13), "fin": date(2026, 11, 13)}, {22}),
        ({"region_id": 2}, {12, 13}),
        ({"service_id": 1}, {10, 11, 14}),
        ({"poste_source_id": 2}, {12, 13}),
        ({"feeder_id": 1}, {10, 14}),
        ({"nature_id": 2}, {11, 13}),
        ({"cause_id": 3}, {12}),
        ({"reseau": "htb"}, {10, 14}),
        ({"reseau": "hta"}, {11, 12, 13}),  # 13 sans cause : HTA
        ({"exogene": True}, {12, 14}),
        ({"exogene": False}, {10, 11, 13}),  # 13 sans cause : non exogène
        ({"reseau": "htb", "exogene": True}, {14}),
        ({"reseau": "hta", "exogene": False}, {11, 13}),
        ({"service_id": 1, "nature_id": 1}, {10, 14}),
        ({"service_id": 2, "reseau": "htb"}, set()),
    ],
)
async def test_appliquer_filtres_sur_donnees(
    db_sqlite: AsyncSession, filtres: dict[str, object], attendus: set[int]
) -> None:
    """Interruptions retenues par chaque combinaison de filtres."""
    from app.models.interruptions import Interruption
    from app.repositories.suivi_incidents_repository import appliquer_filtres

    requete = appliquer_filtres(select(Interruption.id), _filtres(**filtres))
    ids = set((await db_sqlite.execute(requete)).scalars().all())
    assert ids == attendus
