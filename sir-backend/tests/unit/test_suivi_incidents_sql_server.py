"""Requêtes agrégées du « Suivi incidents » (étape 3) compilées pour SQL Server.

SQLite accepte ce que SQL Server refuse (voir CLAUDE.md, erreurs du 27/10, 28/10, 30/10, 19/11) :

- pas de « IS 1 » / « IS 0 » (booléens : ``== true()``) ;
- pas de COALESCE dans le GROUP BY (8120) et toute colonne non agrégée du SELECT est dans le
  GROUP BY (8120) ;
- pas de sous-requête dans un agrégat SUM / COUNT / AVG (130) ;
- sommes d'entiers (clients, minutes) castées en BIGINT ou FLOAT (8115).

Fonctions attendues dans ``app/repositories/suivi_incidents_repository.py`` (chacune renvoie un
``Select`` ou une séquence de ``Select`` à exécuter) :

- ``requete_kpi(filtres: FiltresIncidents)`` ;
- ``requete_natures(filtres: FiltresIncidents)`` (sert aussi aux réseaux HTA / HTB) ;
- ``requete_classement(filtres: FiltresIncidents, niveau: str)`` (service | poste_source | feeder).

Écrits avant le code (circuit « tests avant le code »).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date

import pytest
from sqlalchemy import Select
from sqlalchemy.dialects import mssql

NIVEAUX = ("service", "poste_source", "feeder")
_AGREGATS = ("SUM", "COUNT", "AVG", "MIN", "MAX")


def _filtres(**kwargs: object):
    from app.schemas.suivi_incidents import FiltresIncidents

    return FiltresIncidents(**{"debut": date(2026, 11, 14), "fin": date(2026, 11, 20), **kwargs})


# Variantes de filtres : jointure externe sur causes (réseau, exogène) et égalités
VARIANTES = [
    {},
    {"reseau": "htb"},
    {"reseau": "hta", "exogene": False},
    {"exogene": True, "region_id": 2, "service_id": 3},
    {"poste_source_id": 1, "feeder_id": 2, "nature_id": 3, "cause_id": 4},
]


def _requetes(fabrique: Callable[..., object], *args: object) -> list[Select]:
    resultat = fabrique(*args)
    requetes = list(resultat) if isinstance(resultat, (list, tuple)) else [resultat]
    assert requetes, "aucune requête"
    for requete in requetes:
        assert isinstance(requete, Select), type(requete)
    return requetes


def _sql(requete: Select) -> str:
    """SQL Server, paramètres non liés (deux littéraux identiques restent deux paramètres)."""
    return str(requete.compile(dialect=mssql.dialect()))


def _arguments(sql: str, fonction: str) -> list[str]:
    """Arguments (parenthèses équilibrées) de chaque appel ``fonction(`` du texte."""
    resultats = []
    for m in re.finditer(rf"\b{fonction}\s*\(", sql, re.IGNORECASE):
        profondeur, i = 1, m.end()
        while i < len(sql) and profondeur:
            profondeur += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        resultats.append(sql[m.end() : i - 1])
    return resultats


def _niveau_zero(sql: str) -> str:
    """Texte de la requête la plus externe : le contenu des parenthèses est remplacé par des blancs."""
    sortie, profondeur = [], 0
    for c in sql:
        if c == "(":
            profondeur += 1
            sortie.append(c if profondeur == 1 else " ")
        elif c == ")":
            profondeur -= 1
            sortie.append(c if profondeur == 0 else " ")
        else:
            sortie.append(c if profondeur == 0 else " ")
    return "".join(sortie)


def _clauses_externes(sql: str) -> tuple[str, str | None]:
    """(liste du SELECT, GROUP BY ou None) de la requête externe, texte original conservé."""
    masque = _niveau_zero(sql).upper()
    debut_select = re.search(r"\bSELECT\s", masque)
    assert debut_select, sql
    fin_select = re.search(r"\sFROM\s", masque[debut_select.end() :])
    assert fin_select, sql
    liste_select = sql[debut_select.end() : debut_select.end() + fin_select.start()]
    gb = re.search(r"\sGROUP BY\s", masque)
    if gb is None:
        return liste_select, None
    fin = re.search(r"\s(HAVING|ORDER BY)\s", masque[gb.end() :])
    return liste_select, sql[gb.end() : gb.end() + fin.start() if fin else len(sql)]


def _sans_agregats(texte: str) -> str:
    """Retire les appels d'agrégats (avec leurs arguments) d'une liste du SELECT."""
    for fonction in _AGREGATS:
        for argument in _arguments(texte, fonction):
            texte = re.sub(
                rf"\b{fonction}\s*\(\s*{re.escape(argument)}\s*\)", " ", texte, count=1, flags=re.IGNORECASE
            )
    return texte


_COLONNE = re.compile(r"\b(?:dbo\.)?([a-z_]+)\.([a-z_]+)\b", re.IGNORECASE)


def _colonnes(texte: str) -> set[tuple[str, str]]:
    return {(t.lower(), c.lower()) for t, c in _COLONNE.findall(texte)}


def _controles_communs(sql: str) -> None:
    haut = sql.upper()
    assert " IS 1" not in haut and " IS 0" not in haut, sql
    assert " IS TRUE" not in haut and " IS FALSE" not in haut, sql
    for fonction in _AGREGATS:
        for argument in _arguments(sql, fonction):
            assert "SELECT" not in argument.upper(), f"sous-requête dans {fonction}(…) : {sql}"
    for argument in _arguments(sql, "SUM"):
        bas = argument.lower()
        if "nombre_clients" in bas or "duree_minutes" in bas:
            assert re.search(r"AS (BIGINT|FLOAT)", argument, re.IGNORECASE), (
                f"somme d'entiers sans CAST BIGINT / FLOAT : SUM({argument})"
            )
    for m in re.finditer(r"GROUP BY(.*?)(?:\bHAVING\b|\bORDER BY\b|\)|$)", sql, re.IGNORECASE | re.DOTALL):
        assert "coalesce" not in m.group(1).lower(), f"COALESCE dans le GROUP BY : {sql}"
    liste_select, group_by = _clauses_externes(sql)
    if group_by is not None:
        non_agregees = _colonnes(_sans_agregats(liste_select))
        manquantes = non_agregees - _colonnes(group_by)
        assert not manquantes, f"colonnes du SELECT absentes du GROUP BY {manquantes} : {sql}"


# --------------------------------------------------------------------------------------------
# Les contrôles eux-mêmes (sur des requêtes fautives connues)
# --------------------------------------------------------------------------------------------


def test_les_controles_detectent_les_fautes_connues() -> None:
    """Garde-fou : chaque faute documentée dans CLAUDE.md est bien repérée par ``_controles_communs``."""
    from sqlalchemy import BigInteger, cast, func, select

    from app.models.geo import Service
    from app.models.interruptions import Interruption
    from app.models.referentiel import Cause

    fautives = [
        select(func.count()).where(Cause.est_exogene.is_(True)),
        select(func.coalesce(Interruption.statut, "x"), func.count()).group_by(
            func.coalesce(Interruption.statut, "x")
        ),
        select(func.sum(Interruption.nombre_clients_touches)),
        select(func.sum(Interruption.duree_minutes)),
        select(func.sum(Interruption.id.in_(select(Cause.id)))),
        select(Service.code, Service.libelle, func.count()).group_by(Service.id),
    ]
    for requete in fautives:
        with pytest.raises(AssertionError):
            _controles_communs(_sql(requete))
    _controles_communs(
        _sql(
            select(Service.id, Service.libelle, func.sum(cast(Interruption.nombre_clients_touches, BigInteger)))
            .group_by(Service.id, Service.libelle)
        )
    )


# --------------------------------------------------------------------------------------------
# Requêtes du repository
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_kpi_sql_server(variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_kpi, _filtres(**variante))]
    for sql in textes:
        _controles_communs(sql)
    tout = " ".join(textes)
    # KPI : postes de poste_interruptions, clients sommés en BIGINT (8115), END de la distribution
    assert "poste_interruptions" in tout
    assert "end_mwh" in tout
    # Σ coupures-clients faite par la base ; le CAST BIGINT / FLOAT est vérifié par _controles_communs
    assert any("nombre_clients_touches" in a for a in _arguments(tout, "SUM")), "Σ nombre_clients_touches absente"


@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_natures_sql_server(variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_natures, _filtres(**variante))]
    for sql in textes:
        _controles_communs(sql)
    # agrégation faite par la base (pas une ligne par interruption)
    assert "group by" in " ".join(textes).lower()


@pytest.mark.parametrize("niveau", NIVEAUX)
@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_classement_sql_server(niveau: str, variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_classement, _filtres(**variante), niveau)]
    for sql in textes:
        _controles_communs(sql)
    tout = " ".join(textes).lower()
    table = {"service": "services", "poste_source": "postes_sources", "feeder": "feeders"}[niveau]
    assert re.search(rf"\b{table}\b", tout), f"libellé du niveau {niveau} non lu dans {table}"
    assert "group by" in tout


def test_requete_classement_niveau_inconnu() -> None:
    """Un niveau inconnu n'est jamais traduit en SQL (ValueError, l'API répond 422 avant)."""
    from app.repositories import suivi_incidents_repository as repo

    with pytest.raises((ValueError, KeyError)):
        repo.requete_classement(_filtres(), "region")


def _sql_lie(requete: Select) -> str:
    return str(requete.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.parametrize(
    "fabrique",
    [
        lambda repo, f: repo.requete_kpi(f),
        lambda repo, f: repo.requete_natures(f),
        lambda repo, f: repo.requete_classement(f, "service"),
    ],
    ids=["kpi", "natures", "classement"],
)
def test_requetes_reprennent_appliquer_filtres(fabrique: Callable[..., object]) -> None:
    """Les filtres (période fin incluse, distribution, région imposée) passent par appliquer_filtres."""
    from app.repositories import suivi_incidents_repository as repo

    resultat = fabrique(repo, _filtres(region_id=2, exogene=True))
    requetes = list(resultat) if isinstance(resultat, (list, tuple)) else [resultat]
    for requete in requetes:
        sql = _sql_lie(requete)
        assert "'distribution'" in sql
        assert "2026-11-14" in sql and "2026-11-21" in sql
        assert "interruptions.region_id = 2" in sql
        assert "causes.est_exogene = 1" in sql
        assert "IS 1" not in sql


# --------------------------------------------------------------------------------------------
# Étape 4 — Évolution et Réseau (spécification §9)
#
# - ``requete_evolution(filtres)`` : regroupement par jour (CAST(date_apparition AS DATE), valide
#   sous SQL Server dans le SELECT et le GROUP BY), nature et cause ;
# - ``requete_reseau(filtres, niveau)`` : sommes par poste source ou feeder (niveau feeder : libellé
#   du poste source du feeder lu dans postes_sources) ;
# - ``requete_reseau_postes(filtres, niveau)`` : postes distincts de poste_interruptions par ligne ;
# - niveau inconnu → ValueError (KeyError toléré), jamais traduit en SQL.
# --------------------------------------------------------------------------------------------

NIVEAUX_RESEAU = ("poste_source", "feeder")
_CAST_JOUR = re.compile(r"CAST\s*\(\s*(?:dbo\.)?interruptions\.date_apparition\s+AS\s+DATE\s*\)", re.IGNORECASE)


@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_evolution_sql_server(variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_evolution, _filtres(**variante))]
    for sql in textes:
        _controles_communs(sql)
    assert len(textes) == 1, "une seule requête groupée par jour, nature et cause"
    sql = textes[0]
    liste_select, group_by = _clauses_externes(sql)
    assert group_by is not None, f"agrégation faite par la base : {sql}"
    # jour = CAST(date_apparition AS DATE), dans le SELECT et à l'identique dans le GROUP BY
    assert _CAST_JOUR.search(liste_select), f"jour absent du SELECT : {sql}"
    assert _CAST_JOUR.search(group_by), f"jour absent du GROUP BY : {sql}"
    # libellés de nature et de cause pour categorie_nature
    assert ("natures", "libelle") in _colonnes(group_by), sql
    assert ("causes", "libelle") in _colonnes(group_by), sql
    assert "end_mwh" in sql


@pytest.mark.parametrize("niveau", NIVEAUX_RESEAU)
@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_reseau_sql_server(niveau: str, variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_reseau, _filtres(**variante), niveau)]
    for sql in textes:
        _controles_communs(sql)
    tout = " ".join(textes)
    bas = tout.lower()
    assert "group by" in bas
    table = {"poste_source": "postes_sources", "feeder": "feeders"}[niveau]
    assert re.search(rf"\b{table}\b", bas), f"libellé du niveau {niveau} non lu dans {table}"
    if niveau == "feeder":
        assert re.search(r"\bpostes_sources\b", bas), "libellé du poste source du feeder non lu"
    # Σ coupures-clients faite par la base (CAST BIGINT / FLOAT vérifié par _controles_communs)
    assert any("nombre_clients_touches" in a for a in _arguments(tout, "SUM")), "Σ nombre_clients_touches absente"
    assert "end_mwh" in tout


@pytest.mark.parametrize("niveau", NIVEAUX_RESEAU)
@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_reseau_postes_sql_server(niveau: str, variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    textes = [_sql(r) for r in _requetes(repo.requete_reseau_postes, _filtres(**variante), niveau)]
    for sql in textes:
        _controles_communs(sql)
    tout = " ".join(textes)
    assert "poste_interruptions" in tout
    assert "group by" in tout.lower()
    assert re.search(r"\bDISTINCT\b", tout, re.IGNORECASE), "postes distincts attendus"


@pytest.mark.parametrize("fabrique", ["requete_reseau", "requete_reseau_postes"])
@pytest.mark.parametrize("niveau", ["region", "commune", ""])
def test_requetes_reseau_niveau_inconnu(fabrique: str, niveau: str) -> None:
    from app.repositories import suivi_incidents_repository as repo

    with pytest.raises((ValueError, KeyError)):
        getattr(repo, fabrique)(_filtres(), niveau)


@pytest.mark.parametrize(
    "fabrique",
    [
        lambda repo, f: repo.requete_evolution(f),
        lambda repo, f: repo.requete_reseau(f, "poste_source"),
        lambda repo, f: repo.requete_reseau(f, "feeder"),
        lambda repo, f: repo.requete_reseau_postes(f, "poste_source"),
        lambda repo, f: repo.requete_reseau_postes(f, "feeder"),
    ],
    ids=["evolution", "reseau-poste_source", "reseau-feeder", "postes-poste_source", "postes-feeder"],
)
def test_requetes_etape4_reprennent_appliquer_filtres(fabrique: Callable[..., object]) -> None:
    """Période fin incluse, distribution, région imposée, exogène : par appliquer_filtres."""
    from app.repositories import suivi_incidents_repository as repo

    resultat = fabrique(repo, _filtres(region_id=2, exogene=True))
    requetes = list(resultat) if isinstance(resultat, (list, tuple)) else [resultat]
    assert requetes
    for requete in requetes:
        sql = _sql_lie(requete)
        assert "'distribution'" in sql
        assert "2026-11-14" in sql and "2026-11-21" in sql
        assert "interruptions.region_id = 2" in sql
        assert "causes.est_exogene = 1" in sql
        assert "IS 1" not in sql
