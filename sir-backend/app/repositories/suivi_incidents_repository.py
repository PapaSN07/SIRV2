"""Requêtes du menu « Suivi incidents » : filtres communs aux onglets."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import Select, false, or_, true

from app.models.interruptions import Interruption
from app.models.referentiel import Cause
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


def appliquer_filtres(requete: Select, filtres: FiltresIncidents) -> Select:
    """Restreint une requête partant de ``Interruption`` aux filtres du suivi des incidents.

    Interruptions distribution datées par l'apparition sur [debut, fin] (fin incluse). La
    jointure externe sur ``causes`` n'est ajoutée qu'une fois, et seulement pour le réseau en
    cause ou le facteur exogène : une interruption sans cause reste HTA et non exogène.
    Le périmètre RBAC (services, région de l'utilisateur) est appliqué par l'appelant.
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
        requete = requete.outerjoin(Cause, Cause.id == Interruption.cause_id)
        if filtres.reseau is not None:
            conditions.append(condition_reseau(filtres.reseau))
        if filtres.exogene is True:
            conditions.append(Cause.est_exogene == true())
        elif filtres.exogene is False:
            conditions.append(or_(Cause.est_exogene == false(), Cause.id.is_(None)))

    return requete.where(*conditions)
