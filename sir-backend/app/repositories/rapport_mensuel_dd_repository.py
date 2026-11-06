"""Repository — données du rapport mensuel d'exploitation distribution (Analyse succincte DD).

Une ligne par interruption distribution apparue dans le mois, avec ce que le modèle
« Analyse succincte statistiques exploitation distribution » (PR3-INS-108-a) détaille :
nature, cause, siège, entreprise (agressions), tronçon isolé, départ, service, région.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.geo import Region, Service
from app.models.indicateurs import ObjectifIndicateur
from app.models.interruption_workflow import ETAPE_TRONCONNEMENT, EtapeWorkflow, Workflow
from app.models.interruptions import Interruption, InterruptionDistribution
from app.models.referentiel import Cause, Entreprise, Nature, Siege
from app.models.reseau import Feeder, Troncon
from app.models.sig import TronconSig


@dataclass(frozen=True)
class LigneMensuelle:
    id: int
    date_apparition: datetime
    date_remise: datetime | None
    duree_minutes: int | None
    service_id: int | None
    service_code: str | None
    region_libelle: str | None
    feeder: str | None
    nature: str | None
    cause: str | None
    siege: str | None
    entreprise: str | None
    troncon: str | None
    end_mwh: float
    is_programme: bool = False
    statut: str = ""


def requete_lignes(debut: datetime, fin: datetime):
    """Interruptions distribution apparues dans [debut, fin[, tous statuts."""
    etape = (
        select(EtapeWorkflow.id).where(EtapeWorkflow.code == ETAPE_TRONCONNEMENT).scalar_subquery()
    )
    wf = aliased(Workflow)
    troncon = func.coalesce(
        TronconSig.nom_troncon,
        Troncon.libelle,
        func.nullif(
            func.concat(
                func.coalesce(wf.noeud_amont_libelle, ""),
                literal(" - "),
                func.coalesce(wf.noeud_aval_libelle, ""),
            ),
            " - ",
        ),
    )
    return (
        select(
            Interruption.id,
            Interruption.date_apparition,
            Interruption.date_remise,
            Interruption.duree_minutes,
            Interruption.service_id,
            Service.code.label("service_code"),
            Region.libelle.label("region_libelle"),
            Feeder.libelle.label("feeder"),
            Nature.libelle.label("nature"),
            Cause.libelle.label("cause"),
            Siege.libelle.label("siege"),
            Entreprise.libelle.label("entreprise"),
            troncon.label("troncon"),
            func.coalesce(InterruptionDistribution.end_mwh, 0).label("end_mwh"),
            InterruptionDistribution.is_programme,
            Interruption.statut,
        )
        .select_from(Interruption)
        .outerjoin(Service, Service.id == Interruption.service_id)
        .outerjoin(Region, Region.id == Interruption.region_id)
        .outerjoin(Feeder, Feeder.id == Interruption.feeder_id)
        .outerjoin(Nature, Nature.id == Interruption.nature_id)
        .outerjoin(Cause, Cause.id == Interruption.cause_id)
        .outerjoin(Siege, Siege.id == Interruption.siege_id)
        .outerjoin(Entreprise, Entreprise.id == Interruption.entreprise_id)
        .outerjoin(InterruptionDistribution, InterruptionDistribution.interruption_id == Interruption.id)
        .outerjoin(wf, (wf.interruption_id == Interruption.id) & (wf.etape_workflow_id == etape))
        .outerjoin(TronconSig, TronconSig.id == wf.troncon_sig_id)
        .outerjoin(Troncon, Troncon.id == wf.troncon_id)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.date_apparition >= debut,
            Interruption.date_apparition < fin,
        )
        .order_by(Interruption.date_apparition)
    )


async def lister(db: AsyncSession, debut: datetime, fin: datetime) -> list[LigneMensuelle]:
    rows = (await db.execute(requete_lignes(debut, fin))).all()
    return [
        LigneMensuelle(
            id=int(r.id),
            date_apparition=r.date_apparition,
            date_remise=r.date_remise,
            duree_minutes=r.duree_minutes,
            service_id=r.service_id,
            service_code=r.service_code,
            region_libelle=r.region_libelle,
            feeder=r.feeder,
            nature=r.nature,
            cause=r.cause,
            siege=r.siege,
            entreprise=r.entreprise,
            troncon=r.troncon,
            end_mwh=float(r.end_mwh or 0),
            is_programme=bool(r.is_programme),
            statut=str(r.statut or ""),
        )
        for r in rows
    ]


async def objectif_annuel(db: AsyncSession, annee: int, code: str) -> float | None:
    """Objectif national de l'année (Pilotage) : END en MWh, SAIFI, SAIDI…"""
    valeur = await db.scalar(
        select(ObjectifIndicateur.valeur_annuelle).where(
            ObjectifIndicateur.annee == annee,
            ObjectifIndicateur.code == code,
            ObjectifIndicateur.region_id.is_(None),
        )
    )
    return float(valeur) if valeur is not None else None


async def libelle_region(db: AsyncSession, region_id: int) -> str | None:
    return await db.scalar(select(Region.libelle).where(Region.id == region_id))
