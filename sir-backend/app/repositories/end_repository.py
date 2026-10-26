"""Repository — calcul END (energie_nd)."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.geo import Agence, Service
from app.models.indicateurs import EnergieNd
from app.models.interruptions import (
    Interruption,
    InterruptionDistribution,
    InterruptionTransport,
    PosteInterruption,
)
from app.models.referentiel import TypeEnd
# Ré-export utilisé par les services (end_repo.get_region_id_for_service) : ne pas retirer
from app.repositories.geo_scope_repository import get_region_id_for_service  # noqa: F401


async def get_interruption_for_end(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    """Charge une interruption avec données nécessaires au calcul END."""
    result = await db.execute(
        select(Interruption)
        .options(
            joinedload(Interruption.interruption_distribution),
            joinedload(Interruption.interruption_transport),
            joinedload(Interruption.nature),
            joinedload(Interruption.energie_nd),
            joinedload(Interruption.postes_interrompus).joinedload(PosteInterruption.poste),
            joinedload(Interruption.service)
            .joinedload(Service.agence)
            .joinedload(Agence.delegation),
        )
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction.in_(("distribution", "transport", "omvg")),
        )
    )
    return result.unique().scalar_one_or_none()


async def get_type_end_by_code(db: AsyncSession, code: str) -> TypeEnd | None:
    result = await db.execute(
        select(TypeEnd).where(TypeEnd.code == code, TypeEnd.is_active == True)  # noqa: E712
    )
    return result.scalar_one_or_none()


async def upsert_energie_nd(
    db: AsyncSession,
    *,
    interruption_id: int,
    type_end_id: int | None,
    valeur_mwh: float,
    puissance_coupee_mw: float,
    duree_heures: float,
    est_force_majeure: bool,
) -> EnergieNd:
    result = await db.execute(
        select(EnergieNd).where(EnergieNd.interruption_id == interruption_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.type_end_id = type_end_id
        existing.valeur_mwh = valeur_mwh
        existing.puissance_coupee_mw = puissance_coupee_mw
        existing.duree_heures = duree_heures
        existing.est_force_majeure = est_force_majeure
        existing.calculated_at = datetime.now()
        await db.flush()
        return existing

    record = EnergieNd(
        interruption_id=interruption_id,
        type_end_id=type_end_id,
        valeur_mwh=valeur_mwh,
        puissance_coupee_mw=puissance_coupee_mw,
        duree_heures=duree_heures,
        est_force_majeure=est_force_majeure,
        calculated_at=datetime.now(),
    )
    db.add(record)
    await db.flush()
    return record


async def mirror_end_mwh(
    db: AsyncSession,
    interruption_id: int,
    end_mwh: float,
) -> None:
    result = await db.execute(
        select(InterruptionDistribution).where(
            InterruptionDistribution.interruption_id == interruption_id
        )
    )
    distribution = result.scalar_one_or_none()
    if distribution is not None:
        distribution.end_mwh = end_mwh
        await db.flush()
        return

    result = await db.execute(
        select(InterruptionTransport).where(
            InterruptionTransport.interruption_id == interruption_id
        )
    )
    transport = result.scalar_one_or_none()
    if transport is not None:
        transport.energie_non_fournie_mwh = end_mwh
        await db.flush()
