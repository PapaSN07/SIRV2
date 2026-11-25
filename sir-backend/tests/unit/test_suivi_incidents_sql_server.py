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


# --------------------------------------------------------------------------------------------
# Étape 5 — SAIFI / SAIDI (spécification §10)
#
# ``requete_saifi(filtres, service_ids, regroupement)`` renvoie **un** ``Select`` :
# - regroupement ``None`` (une ligne), ``"nature"`` (natures.libelle, causes.libelle), ``"jour"``
#   (``jour_de(date_apparition)`` = CAST(… AS DATE)), ``"service"`` (services.id, code, libelle) ;
# - conditions : ``appliquer_filtres`` + ``interruptions_du_perimetre(service_ids)`` (région posée
#   par ``perimetre``) + ``_distribution_saifi_saidi()`` (statut clôturé, date_remise renseignée,
#   durée > 5 min) ;
# - NombreClient = Σ clients estimés des postes (``_clients_poste``, CAST BIGINT) et
#   Σ NombreClient × durée (CAST FLOAT) : dépassement INT 8115 ;
# - regroupement inconnu → ValueError (KeyError toléré), jamais traduit en SQL.
# --------------------------------------------------------------------------------------------

REGROUPEMENTS_SAIFI = (None, "nature", "jour", "service")
SERVICES_PERIMETRE = [1, 2]


def _requete_saifi(filtres: object, regroupement: str | None) -> Select:
    from app.repositories import suivi_incidents_repository as repo

    requete = repo.requete_saifi(filtres, SERVICES_PERIMETRE, regroupement)
    assert isinstance(requete, Select), f"un seul Select attendu, reçu {type(requete)}"
    return requete


@pytest.mark.parametrize("regroupement", REGROUPEMENTS_SAIFI, ids=lambda r: r or "aucun")
@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_saifi_sql_server(regroupement: str | None, variante: dict[str, object]) -> None:
    from app.repositories.perimetre import perimetre_region

    with perimetre_region(None):
        sql = _sql(_requete_saifi(_filtres(**variante), regroupement))
    _controles_communs(sql)
    sommes = _arguments(sql, "SUM")
    # Σ clients estimés des postes en BIGINT, Σ clients × durée en FLOAT
    assert any(
        "nombre_clients_estime" in a and re.search(r"AS BIGINT", a, re.IGNORECASE) for a in sommes
    ), f"Σ nombre_clients_estime sans CAST BIGINT : {sql}"
    assert any(
        "duree_minutes" in a and re.search(r"AS FLOAT", a, re.IGNORECASE) for a in sommes
    ), f"Σ clients × durée sans CAST FLOAT : {sql}"
    assert "poste_interruptions" in sql

    liste_select, group_by = _clauses_externes(sql)
    if regroupement is None:
        assert group_by is None, f"une seule ligne attendue (pas de GROUP BY) : {sql}"
        return
    assert group_by is not None, f"agrégation faite par la base : {sql}"
    colonnes_gb = _colonnes(group_by)
    if regroupement == "nature":
        assert ("natures", "libelle") in colonnes_gb, sql
        assert ("causes", "libelle") in colonnes_gb, sql
    elif regroupement == "jour":
        assert _CAST_JOUR.search(liste_select), f"jour absent du SELECT : {sql}"
        assert _CAST_JOUR.search(group_by), f"jour absent du GROUP BY : {sql}"
    else:
        assert ("services", "id") in colonnes_gb, sql
        assert re.search(r"\bservices\b", sql.lower()), "libellé du service non lu dans services"


@pytest.mark.parametrize("regroupement", REGROUPEMENTS_SAIFI, ids=lambda r: r or "aucun")
def test_requete_saifi_regles_de_la_formule(regroupement: str | None) -> None:
    """Filtres (appliquer_filtres), périmètre, clôturées, remise renseignée, durée > 5 min."""
    from app.repositories.perimetre import perimetre_region

    with perimetre_region(None):
        sql = _sql_lie(_requete_saifi(_filtres(region_id=2, exogene=True), regroupement))
    # appliquer_filtres : distribution, période fin incluse, région, exogène
    assert "'distribution'" in sql
    assert "2026-11-14" in sql and "2026-11-21" in sql
    assert "interruptions.region_id = 2" in sql
    assert "causes.est_exogene = 1" in sql
    assert "IS 1" not in sql
    # périmètre : services du dénominateur
    assert re.search(r"interruptions\.service_id IN \(1, 2\)", sql), sql
    # _distribution_saifi_saidi : statut clôturé, date de remise, durée > 5 minutes
    assert re.search(r"interruptions\.statut IN \(N?'cloture', N?'valide', N?'archive'\)", sql), sql
    assert re.search(r"interruptions\.date_remise IS NOT NULL", sql), sql
    assert re.search(r"coalesce\((?:dbo\.)?interruptions\.duree_minutes, 0\) > 5\b", sql, re.IGNORECASE), sql


@pytest.mark.parametrize("regroupement", REGROUPEMENTS_SAIFI, ids=lambda r: r or "aucun")
def test_requete_saifi_region_du_perimetre(regroupement: str | None) -> None:
    """En régional, la région posée par ``perimetre`` filtre l'interruption même sans filtre region_id."""
    from app.repositories.perimetre import perimetre_region

    with perimetre_region(1):
        sql = _sql_lie(_requete_saifi(_filtres(), regroupement))
    assert "interruptions.region_id = 1" in sql, sql
    with perimetre_region(None):
        sql = _sql_lie(_requete_saifi(_filtres(), regroupement))
    assert "interruptions.region_id" not in sql.split("WHERE", 1)[1], sql


@pytest.mark.parametrize("regroupement", ["region", "mois", "", "poste_source"])
def test_requete_saifi_regroupement_inconnu(regroupement: str) -> None:
    from app.repositories import suivi_incidents_repository as repo

    with pytest.raises((ValueError, KeyError)):
        repo.requete_saifi(_filtres(), SERVICES_PERIMETRE, regroupement)


# --------------------------------------------------------------------------------------------
# Étape 6a — Carte et Localisation (spécification §11)
#
# - ``requete_postes_touches(filtres)`` : **un** ``Select`` groupé par poste (postes.id, code,
#   libellé, feeder **du poste** — jointure ``feeders.id = postes.feeder_id`` — et son libellé,
#   poste source de ce feeder et son libellé) ; interruptions distinctes (COUNT DISTINCT),
#   Σ durée (CAST BIGINT / FLOAT), Σ clients du poste (estimés, sinon touchés : CAST BIGINT) ;
# - ``requete_postes_natures(filtres)`` : **un** ``Select`` groupé par (poste, natures.libelle,
#   causes.libelle) ;
# - ``requete_rapprochement_sig(poste_ids)`` : **liste** de ``Select`` (une par lot de 500
#   identifiants au plus, limite de 2 100 paramètres de SQL Server) ; liste vide sans identifiant.
#   Vérification : compilé avec ``literal_binds``, chaque ``IN (…)`` contient au plus 500 valeurs et
#   l'union des lots couvre tous les identifiants, chacun une fois ; nœud actif ``= 1`` (jamais IS 1).
# --------------------------------------------------------------------------------------------

_JOINTURE_FEEDER_DU_POSTE = re.compile(
    r"(?:dbo\.)?feeders\.id\s*=\s*(?:dbo\.)?postes\.feeder_id"
    r"|(?:dbo\.)?postes\.feeder_id\s*=\s*(?:dbo\.)?feeders\.id",
    re.IGNORECASE,
)
_JOINTURE_PS_DU_FEEDER = re.compile(
    r"(?:dbo\.)?postes_sources\.id\s*=\s*(?:dbo\.)?feeders\.poste_source_id"
    r"|(?:dbo\.)?feeders\.poste_source_id\s*=\s*(?:dbo\.)?postes_sources\.id",
    re.IGNORECASE,
)


def _un_select(fabrique: Callable[..., object], *args: object) -> Select:
    requete = fabrique(*args)
    assert isinstance(requete, Select), f"un seul Select attendu, reçu {type(requete)}"
    return requete


@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_postes_touches_sql_server(variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    sql = _sql(_un_select(repo.requete_postes_touches, _filtres(**variante)))
    _controles_communs(sql)
    liste_select, group_by = _clauses_externes(sql)
    assert group_by is not None, f"agrégation par poste faite par la base : {sql}"
    colonnes_gb = _colonnes(group_by)
    assert ("postes", "id") in colonnes_gb, sql
    # Feeder et poste source **du poste** (pas ceux de l'interruption)
    assert _JOINTURE_FEEDER_DU_POSTE.search(sql), f"feeder du poste non joint par postes.feeder_id : {sql}"
    assert _JOINTURE_PS_DU_FEEDER.search(sql), f"poste source du feeder non joint : {sql}"
    assert {("feeders", "libelle"), ("postes_sources", "libelle")} <= _colonnes(liste_select), sql
    # Interruptions distinctes, Σ durée et Σ clients du poste (CAST vérifiés par _controles_communs)
    assert any(
        re.search(r"DISTINCT\s*\(?\s*(?:dbo\.)?interruptions\.id\b", a, re.IGNORECASE)
        for a in _arguments(sql, "COUNT")
    ), f"COUNT(DISTINCT interruptions.id) attendu : {sql}"
    sommes = _arguments(sql, "SUM")
    assert any("duree_minutes" in a for a in sommes), f"Σ durée absente : {sql}"
    assert any(
        "nombre_clients_estime" in a and "poste_interruptions.nombre_clients_touches" in a for a in sommes
    ), f"Σ clients du poste (estimés, sinon touchés du poste) absente : {sql}"
    assert "poste_interruptions" in sql


@pytest.mark.parametrize("variante", VARIANTES, ids=lambda v: ",".join(v) or "aucun")
def test_requete_postes_natures_sql_server(variante: dict[str, object]) -> None:
    from app.repositories import suivi_incidents_repository as repo

    sql = _sql(_un_select(repo.requete_postes_natures, _filtres(**variante)))
    _controles_communs(sql)
    _, group_by = _clauses_externes(sql)
    assert group_by is not None, f"agrégation faite par la base : {sql}"
    colonnes_gb = _colonnes(group_by)
    assert ("natures", "libelle") in colonnes_gb, sql
    assert ("causes", "libelle") in colonnes_gb, sql
    assert colonnes_gb & {("postes", "id"), ("poste_interruptions", "poste_id")}, f"poste absent du GROUP BY : {sql}"
    assert "poste_interruptions" in sql


@pytest.mark.parametrize(
    "fabrique",
    [lambda repo, f: repo.requete_postes_touches(f), lambda repo, f: repo.requete_postes_natures(f)],
    ids=["postes_touches", "postes_natures"],
)
def test_requetes_etape6a_reprennent_appliquer_filtres(fabrique: Callable[..., object]) -> None:
    """Période fin incluse, distribution, région imposée, exogène : par appliquer_filtres."""
    from app.repositories import suivi_incidents_repository as repo

    sql = _sql_lie(fabrique(repo, _filtres(region_id=2, exogene=True)))
    assert "'distribution'" in sql
    assert "2026-11-14" in sql and "2026-11-21" in sql
    assert "interruptions.region_id = 2" in sql
    assert "causes.est_exogene = 1" in sql
    assert "IS 1" not in sql
    # une seule jointure sur causes (cause_jointe quand la requête la joint déjà)
    assert len(re.findall(r"JOIN\s+(?:dbo\.)?causes\b", sql, re.IGNORECASE)) <= 1, sql


def _valeurs_in(sql: str) -> list[list[int]]:
    """Valeurs de chaque ``IN (…)`` d'entiers d'un SQL compilé avec literal_binds (les ``IN`` de
    textes, par exemple ``rapprochement_sig IN ('auto', 'manuel')``, sont ignorés)."""
    listes = []
    for argument in _arguments(sql, "IN"):
        if re.fullmatch(r"\s*-?\d+(?:\s*,\s*-?\d+)*\s*", argument):
            listes.append([int(v) for v in re.findall(r"-?\d+", argument)])
    return listes


@pytest.mark.parametrize("nombre", [1, 499, 500, 501, 1200])
def test_requete_rapprochement_sig_lots_de_500(nombre: int) -> None:
    from app.repositories import suivi_incidents_repository as repo

    ids = list(range(1, nombre + 1))
    requetes = repo.requete_rapprochement_sig(ids)
    assert isinstance(requetes, (list, tuple)), f"liste de Select attendue, reçu {type(requetes)}"
    assert len(requetes) == -(-nombre // 500), "un Select par lot de 500 identifiants"
    vus: list[int] = []
    for requete in requetes:
        assert isinstance(requete, Select), type(requete)
        sql = _sql_lie(requete)
        listes = _valeurs_in(sql)
        assert len(listes) == 1, f"un seul filtre IN d'identifiants de postes attendu : {sql[:500]}"
        assert len(listes[0]) <= 500, f"IN de {len(listes[0])} valeurs (> 500)"
        vus.extend(listes[0])
    assert sorted(vus) == ids, "chaque identifiant dans un lot, une seule fois"


def test_requete_rapprochement_sig_sans_identifiant() -> None:
    from app.repositories import suivi_incidents_repository as repo

    assert list(repo.requete_rapprochement_sig([])) == []


def test_requete_rapprochement_sig_sql_server() -> None:
    from app.repositories import suivi_incidents_repository as repo

    (requete,) = repo.requete_rapprochement_sig([1, 2, 3])
    sql = _sql(requete)
    _controles_communs(sql)
    bas = sql.lower()
    assert re.search(r"\bschema_unifilaire_postes\b", bas), sql
    assert re.search(r"\bnoeuds_sig\b", bas), sql
    colonnes = _colonnes(_clauses_externes(sql)[0])
    assert ("schema_unifilaire_postes", "poste_id") in colonnes, sql
    assert {("noeuds_sig", "coord_x"), ("noeuds_sig", "coord_y")} <= colonnes, sql
    lie = _sql_lie(requete)
    assert "noeuds_sig.est_actif = 1" in lie, f"nœud actif attendu (== true()) : {lie}"
    assert "IS 1" not in lie and "IS 0" not in lie
