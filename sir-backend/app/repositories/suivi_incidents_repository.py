"""Requêtes du menu « Suivi incidents » : filtres communs aux onglets."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import BigInteger, Date, Float, Select, cast, false, func, null, or_, select, true
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement, FunctionElement

from app.models.geo import Service
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder, Poste, PosteSource
from app.models.schema_unifilaire import SchemaUnifilairePoste
from app.models.sig import NoeudSig
from app.repositories.perimetre import interruptions_du_perimetre
from app.repositories.pilotage_repository import (
    _clients_poste,
    _distribution_saifi_saidi,
    _sommes_clients,
    condition_reseau,
)
from app.schemas.suivi_incidents import FiltresIncidents

_FILTRES_EGALITE = (
    ("region_id", Interruption.region_id),
    ("service_id", Interruption.service_id),
    ("poste_source_id", Interruption.poste_source_id),
    ("feeder_id", Interruption.feeder_id),
    ("nature_id", Interruption.nature_id),
    ("cause_id", Interruption.cause_id),
)


def appliquer_filtres(requete: Select, filtres: FiltresIncidents, *, cause_jointe: bool = False) -> Select:
    """Restreint une requête partant de ``Interruption`` aux filtres du suivi des incidents.

    Interruptions distribution datées par l'apparition sur [debut, fin] (fin incluse). La
    jointure externe sur ``causes`` n'est ajoutée qu'une fois, et seulement pour le réseau en
    cause ou le facteur exogène : une interruption sans cause reste HTA et non exogène.
    ``cause_jointe`` : la requête joint déjà ``causes`` en externe (pas de seconde jointure).
    Le périmètre RBAC (région / service imposés) arrive par les filtres résolus.
    """
    debut = datetime(filtres.debut.year, filtres.debut.month, filtres.debut.day)
    fin_exclue = datetime(filtres.fin.year, filtres.fin.month, filtres.fin.day) + timedelta(days=1)
    conditions = [
        Interruption.type_direction == "distribution",
        Interruption.date_apparition >= debut,
        Interruption.date_apparition < fin_exclue,
    ]
    for champ, colonne in _FILTRES_EGALITE:
        valeur = getattr(filtres, champ)
        if valeur is not None:
            conditions.append(colonne == valeur)

    if filtres.reseau is not None or filtres.exogene is not None:
        if not cause_jointe:
            requete = requete.outerjoin(Cause, Cause.id == Interruption.cause_id)
        if filtres.reseau is not None:
            conditions.append(condition_reseau(filtres.reseau))
        if filtres.exogene is True:
            conditions.append(Cause.est_exogene == true())
        elif filtres.exogene is False:
            conditions.append(or_(Cause.est_exogene == false(), Cause.id.is_(None)))

    return requete.where(*conditions)


# ── Agrégats de l'onglet Vue d'ensemble ────────────────────────────────────────────────────
# Sommes d'entiers castées (dépassement INT 8115), END en FLOAT ; pas de sous-requête dans un
# agrégat ni de COALESCE dans un GROUP BY (pièges SQL Server, CLAUDE.md).

def _sommes() -> tuple:
    return (
        func.count(Interruption.id).label("nombre"),
        func.sum(cast(Interruption.duree_minutes, BigInteger)).label("duree_minutes"),
        func.sum(cast(InterruptionDistribution.end_mwh, Float)).label("end_mwh"),
    )


def _avec_distribution(requete: Select) -> Select:
    return requete.outerjoin(InterruptionDistribution, InterruptionDistribution.interruption_id == Interruption.id)


def requete_kpi(filtres: FiltresIncidents) -> tuple[Select, Select]:
    """(agrégats par interruption, postes touchés distincts)."""
    agregats = _avec_distribution(
        select(
            *_sommes(),
            func.avg(cast(Interruption.duree_minutes, Float)).label("duree_moyenne_minutes"),
            func.sum(cast(Interruption.nombre_clients_touches, BigInteger)).label("coupures_clients"),
        ).select_from(Interruption)
    )
    postes = select(func.count(func.distinct(PosteInterruption.poste_id)).label("postes")).select_from(
        Interruption
    ).join(PosteInterruption, PosteInterruption.interruption_id == Interruption.id)
    return appliquer_filtres(agregats, filtres), appliquer_filtres(postes, filtres)


def requete_natures(filtres: FiltresIncidents) -> Select:
    """Sommes par (nature, cause) : la catégorie et le réseau se déduisent des libellés."""
    requete = _avec_distribution(
        select(Nature.libelle.label("nature"), Cause.libelle.label("cause"), *_sommes())
        .select_from(Interruption)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
    )
    return appliquer_filtres(requete, filtres, cause_jointe=True).group_by(Nature.libelle, Cause.libelle)


_NIVEAUX_CLASSEMENT = {
    "service": (Service, Interruption.service_id),
    "poste_source": (PosteSource, Interruption.poste_source_id),
    "feeder": (Feeder, Interruption.feeder_id),
}


def requete_classement(filtres: FiltresIncidents, niveau: str) -> Select:
    """Sommes par service, poste source ou feeder (ligne sans rattachement : id NULL)."""
    if niveau not in _NIVEAUX_CLASSEMENT:
        raise ValueError(f"Niveau de classement inconnu : {niveau}")
    modele, colonne = _NIVEAUX_CLASSEMENT[niveau]
    requete = _avec_distribution(
        select(modele.id.label("id"), modele.code.label("code"), modele.libelle.label("libelle"), *_sommes())
        .select_from(Interruption)
        .outerjoin(modele, modele.id == colonne)
    )
    return appliquer_filtres(requete, filtres).group_by(modele.id, modele.code, modele.libelle)


# ── Onglets Évolution et Réseau ────────────────────────────────────────────────────────────


class jour_de(FunctionElement):  # noqa: N801 — construction SQL, nommée comme une fonction
    """Jour d'un DATETIME2 : ``CAST(x AS DATE)`` (SQL Server), ``date(x)`` (SQLite des tests).

    Sous SQLite, ``CAST('2026-11-20 23:59:00' AS DATE)`` donne 2026 : un ``cast`` brut serait faux.
    """

    type = Date()
    inherit_cache = True


@compiles(jour_de)
def _jour_de_defaut(element: jour_de, compiler, **kw) -> str:  # type: ignore[no-untyped-def]
    return f"CAST({compiler.process(element.clauses, **kw)} AS DATE)"


@compiles(jour_de, "sqlite")
def _jour_de_sqlite(element: jour_de, compiler, **kw) -> str:  # type: ignore[no-untyped-def]
    return f"date({compiler.process(element.clauses, **kw)})"


def requete_evolution(filtres: FiltresIncidents) -> Select:
    """Sommes par (jour, nature, cause) ; regroupement en semaines / mois et catégories en Python."""
    jour = jour_de(Interruption.date_apparition)
    requete = _avec_distribution(
        select(jour.label("jour"), Nature.libelle.label("nature"), Cause.libelle.label("cause"), *_sommes())
        .select_from(Interruption)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
    )
    return appliquer_filtres(requete, filtres, cause_jointe=True).group_by(
        jour_de(Interruption.date_apparition), Nature.libelle, Cause.libelle
    )


_NIVEAUX_RESEAU = {
    "poste_source": (PosteSource, Interruption.poste_source_id),
    "feeder": (Feeder, Interruption.feeder_id),
}


def _niveau_reseau(niveau: str) -> tuple[type, ColumnElement]:
    if niveau not in _NIVEAUX_RESEAU:
        raise ValueError(f"Niveau du tableau Réseau inconnu : {niveau}")
    return _NIVEAUX_RESEAU[niveau]


def requete_reseau(filtres: FiltresIncidents, niveau: str) -> Select:
    """Sommes par poste source ou par feeder (avec le libellé du poste source du feeder)."""
    modele, colonne = _niveau_reseau(niveau)
    colonnes_ligne = [modele.id.label("id"), modele.code.label("code"), modele.libelle.label("libelle")]
    requete = (
        select(
            *colonnes_ligne,
            (PosteSource.libelle if modele is Feeder else null()).label("poste_source"),
            *_sommes(),
            func.sum(cast(Interruption.nombre_clients_touches, BigInteger)).label("coupures_clients"),
        )
        .select_from(Interruption)
        .outerjoin(modele, modele.id == colonne)
    )
    groupes = [modele.id, modele.code, modele.libelle]
    if modele is Feeder:
        requete = requete.outerjoin(PosteSource, PosteSource.id == Feeder.poste_source_id)
        groupes.append(PosteSource.libelle)
    return appliquer_filtres(_avec_distribution(requete), filtres).group_by(*groupes)


def requete_reseau_postes(filtres: FiltresIncidents, niveau: str) -> Select:
    """Postes distincts touchés par ligne (identifiant du poste source / feeder de l'interruption)."""
    _, colonne = _niveau_reseau(niveau)
    requete = (
        select(colonne.label("id"), func.count(func.distinct(PosteInterruption.poste_id)).label("postes"))
        .select_from(Interruption)
        .join(PosteInterruption, PosteInterruption.interruption_id == Interruption.id)
    )
    return appliquer_filtres(requete, filtres).group_by(colonne)


# ── Onglet SAIFI / SAIDI ──────────────────────────────────────────────────────────────────

REGROUPEMENTS_SAIFI = (None, "nature", "jour", "service")


def requete_saifi(filtres: FiltresIncidents, service_ids: list[int], regroupement: str | None = None) -> Select:
    """Numérateurs SAIFI / SAIDI (formule SENELEC) des interruptions du périmètre et des filtres.

    Mêmes sommes et mêmes exclusions que ``pilotage_repository.requete_sommes_clients`` (clôturées,
    plus de 5 minutes, clients estimés des postes) ; ``regroupement`` : aucun, (nature, cause),
    jour d'apparition ou service. Le périmètre (services, région posée par
    ``indicateurs_service._load_service_ids``) vient de ``interruptions_du_perimetre``.
    """
    if regroupement not in REGROUPEMENTS_SAIFI:
        raise ValueError(f"Regroupement SAIFI inconnu : {regroupement}")
    colonnes: list = []
    groupes: list = []
    requete_base = None
    if regroupement == "nature":
        colonnes = [Nature.libelle.label("nature"), Cause.libelle.label("cause")]
        groupes = [Nature.libelle, Cause.libelle]
    elif regroupement == "jour":
        colonnes = [jour_de(Interruption.date_apparition).label("jour")]
        groupes = [jour_de(Interruption.date_apparition)]
    elif regroupement == "service":
        colonnes = [Service.id.label("id"), Service.code.label("code"), Service.libelle.label("libelle")]
        groupes = [Service.id, Service.code, Service.libelle]
    requete_base = (
        select(*colonnes, *_sommes_clients())
        .select_from(Interruption)
        .outerjoin(PosteInterruption, PosteInterruption.interruption_id == Interruption.id)
    )
    if regroupement == "nature":
        requete_base = requete_base.outerjoin(Nature, Nature.id == Interruption.nature_id).outerjoin(
            Cause, Cause.id == Interruption.cause_id
        )
    elif regroupement == "service":
        requete_base = requete_base.outerjoin(Service, Service.id == Interruption.service_id)
    requete = appliquer_filtres(requete_base, filtres, cause_jointe=regroupement == "nature").where(
        interruptions_du_perimetre(service_ids), *_distribution_saifi_saidi()
    )
    return requete.group_by(*groupes) if groupes else requete


# ── Onglets Carte et Localisation ─────────────────────────────────────────────────────────

# SQL Server : 2 100 paramètres au plus par requête
TAILLE_LOT_IDS = 500
RAPPROCHEMENTS_SIG_RETENUS = ("auto", "manuel")


def requete_postes_touches(filtres: FiltresIncidents) -> Select:
    """Postes des interruptions filtrées : feeder et poste source **du poste**, interruptions
    distinctes, Σ durée (minutes) et Σ clients du poste (estimés, sinon touchés)."""
    requete = (
        select(
            Poste.id.label("poste_id"),
            Poste.code.label("code"),
            Poste.libelle.label("libelle"),
            Poste.feeder_id.label("feeder_id"),
            Feeder.libelle.label("feeder"),
            PosteSource.id.label("poste_source_id"),
            PosteSource.libelle.label("poste_source"),
            func.count(func.distinct(Interruption.id)).label("nombre"),
            func.sum(cast(Interruption.duree_minutes, BigInteger)).label("duree_minutes"),
            func.sum(_clients_poste()).label("clients"),
        )
        .select_from(Interruption)
        .join(PosteInterruption, PosteInterruption.interruption_id == Interruption.id)
        .join(Poste, Poste.id == PosteInterruption.poste_id)
        .outerjoin(Feeder, Feeder.id == Poste.feeder_id)
        .outerjoin(PosteSource, PosteSource.id == Feeder.poste_source_id)
    )
    return appliquer_filtres(requete, filtres).group_by(
        Poste.id, Poste.code, Poste.libelle, Poste.feeder_id, Feeder.libelle, PosteSource.id, PosteSource.libelle
    )


def requete_postes_natures(filtres: FiltresIncidents) -> Select:
    """Interruptions distinctes par (poste, nature, cause) : nature dominante d'un poste."""
    requete = (
        select(
            PosteInterruption.poste_id.label("poste_id"),
            Nature.libelle.label("nature"),
            Cause.libelle.label("cause"),
            func.count(func.distinct(Interruption.id)).label("nombre"),
        )
        .select_from(Interruption)
        .join(PosteInterruption, PosteInterruption.interruption_id == Interruption.id)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
    )
    return appliquer_filtres(requete, filtres, cause_jointe=True).group_by(
        PosteInterruption.poste_id, Nature.libelle, Cause.libelle
    )


def requete_rapprochement_sig(poste_ids: list[int]) -> list[Select]:
    """Coordonnées des nœuds SIG rapprochés (auto / manuel, nœud actif), un Select par lot de 500 postes.

    Lignes triées par poste puis par id de rapprochement : la première exploitable fait foi.
    """
    ids = sorted(set(poste_ids))
    return [
        select(
            SchemaUnifilairePoste.poste_id.label("poste_id"),
            SchemaUnifilairePoste.id.label("rapprochement_id"),
            NoeudSig.coord_x.label("coord_x"),
            NoeudSig.coord_y.label("coord_y"),
        )
        .join(NoeudSig, NoeudSig.id == SchemaUnifilairePoste.noeud_sig_id)
        .where(
            SchemaUnifilairePoste.poste_id.in_(ids[debut : debut + TAILLE_LOT_IDS]),
            SchemaUnifilairePoste.rapprochement_sig.in_(RAPPROCHEMENTS_SIG_RETENUS),
            NoeudSig.est_actif == true(),
            NoeudSig.coord_x.isnot(None),
            NoeudSig.coord_y.isnot(None),
        )
        .order_by(SchemaUnifilairePoste.poste_id, SchemaUnifilairePoste.id)
        for debut in range(0, len(ids), TAILLE_LOT_IDS)
    ]

