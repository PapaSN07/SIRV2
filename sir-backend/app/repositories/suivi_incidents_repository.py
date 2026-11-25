"""Requêtes du menu « Suivi incidents » : filtres communs aux onglets."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import BigInteger, Float, Select, cast, false, func, or_, select, true

from app.models.geo import Service
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.referentiel import Cause, Nature
from app.models.reseau import Feeder, PosteSource
from app.repositories.pilotage_repository import condition_reseau
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
