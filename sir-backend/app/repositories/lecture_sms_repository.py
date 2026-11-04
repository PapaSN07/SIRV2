"""Repository — référentiels lus pour reconnaître une interruption dans un SMS (départs, causes)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.geo import Region, Service
from app.models.interruptions import Interruption
from app.models.referentiel import Cause
from app.models.reseau import Feeder, PosteSource

_EXPLOITATION = ("DAKAR", "REGIONS")


@dataclass(frozen=True)
class DepartRef:
    id: int
    code: str
    libelle: str
    poste_source_id: int
    poste_source_libelle: str
    region_id: int | None


@dataclass(frozen=True)
class CauseRef:
    id: int
    libelle: str


@dataclass(frozen=True)
class InterruptionEnCoursRef:
    id: int
    numero_interruption: int
    date_apparition: datetime


def requete_departs():
    """Départs actifs avec leur poste source et leur région d'exploitation.

    Région : même règle que ``interruption_distribution_repository.region_du_depart``
    (région propre du départ, sinon celle de son service, sinon celle de son poste source).
    """
    r_depart = aliased(Region)
    r_service = aliased(Region)
    r_poste = aliased(Region)
    requete = (
        select(
            Feeder.id,
            Feeder.code,
            Feeder.libelle,
            Feeder.poste_source_id,
            PosteSource.libelle,
            func.coalesce(r_depart.id, r_service.id, r_poste.id),
        )
        .join(PosteSource, PosteSource.id == Feeder.poste_source_id)
        .outerjoin(r_depart, (r_depart.id == Feeder.region_id) & r_depart.code.in_(_EXPLOITATION))
        .outerjoin(Service, Service.id == Feeder.service_id)
        .outerjoin(r_service, (r_service.id == Service.region_id) & r_service.code.in_(_EXPLOITATION))
        .outerjoin(r_poste, (r_poste.id == PosteSource.region_id) & r_poste.code.in_(_EXPLOITATION))
        .where(Feeder.is_active == true())
    )
    return requete


async def lister_departs(db: AsyncSession) -> list[DepartRef]:
    lignes = (await db.execute(requete_departs())).all()
    return [
        DepartRef(
            id=int(i),
            code=str(code or ""),
            libelle=str(lib or ""),
            poste_source_id=int(ps),
            poste_source_libelle=str(ps_lib or ""),
            region_id=int(reg) if reg is not None else None,
        )
        for i, code, lib, ps, ps_lib, reg in lignes
    ]


async def lister_causes_distribution(db: AsyncSession) -> list[CauseRef]:
    requete = select(Cause.id, Cause.libelle).where(
        Cause.is_active == true(), Cause.type_reseau.in_(("distribution", "commun"))
    )
    return [CauseRef(id=int(i), libelle=str(lib)) for i, lib in (await db.execute(requete)).all()]


async def interruption_en_cours_du_depart(db: AsyncSession, feeder_id: int) -> InterruptionEnCoursRef | None:
    """Dernière interruption de distribution encore en cours sur ce départ."""
    requete = (
        select(Interruption.id, Interruption.numero_interruption, Interruption.date_apparition)
        .where(
            Interruption.type_direction == "distribution",
            Interruption.feeder_id == feeder_id,
            Interruption.statut == "en_cours",
        )
        .order_by(Interruption.date_apparition.desc())
        .limit(1)
    )
    ligne = (await db.execute(requete)).first()
    if ligne is None:
        return None
    return InterruptionEnCoursRef(id=int(ligne[0]), numero_interruption=int(ligne[1]), date_apparition=ligne[2])
