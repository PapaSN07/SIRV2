"""Repository — calcul et persistance SAIFI/SAIDI."""

from datetime import datetime

from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.geo import Agence, Delegation, Service
from app.models.indicateurs import NombreClientMois, SaifiSaidi
from app.models.interruptions import Interruption, PosteInterruption


async def get_interruption_for_saifi_saidi(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    result = await db.execute(
        select(Interruption)
        .options(
            joinedload(Interruption.postes_interrompus).joinedload(PosteInterruption.poste),
        )
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction == "distribution",
        )
    )
    return result.unique().scalar_one_or_none()


async def get_nombre_clients_reference(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
) -> int | None:
    result = await db.execute(
        select(NombreClientMois.nombre_clients).where(
            NombreClientMois.service_id == service_id,
            NombreClientMois.annee == annee,
            NombreClientMois.mois == mois,
        )
    )
    return result.scalar_one_or_none()


async def list_validated_interruptions_for_service_period(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
) -> list[Interruption]:
    result = await db.execute(
        select(Interruption)
        .options(joinedload(Interruption.postes_interrompus))
        .where(
            Interruption.type_direction == "distribution",
            Interruption.statut == "valide",
            Interruption.service_id == service_id,
            extract("year", Interruption.date_apparition) == annee,
            extract("month", Interruption.date_apparition) == mois,
        )
    )
    return list(result.unique().scalars().all())


async def upsert_saifi_saidi(
    db: AsyncSession,
    *,
    service_id: int,
    annee: int,
    mois: int,
    saifi: float,
    saidi: float,
    nombre_interruptions: int,
    total_clients_reference: int,
) -> SaifiSaidi:
    result = await db.execute(
        select(SaifiSaidi).where(
            SaifiSaidi.service_id == service_id,
            SaifiSaidi.annee == annee,
            SaifiSaidi.mois == mois,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        existing.saifi = saifi
        existing.saidi = saidi
        existing.nombre_interruptions = nombre_interruptions
        existing.total_clients_reference = total_clients_reference
        existing.calculated_at = datetime.now()
        await db.flush()
        return existing

    record = SaifiSaidi(
        service_id=service_id,
        annee=annee,
        mois=mois,
        saifi=saifi,
        saidi=saidi,
        nombre_interruptions=nombre_interruptions,
        total_clients_reference=total_clients_reference,
        calculated_at=datetime.now(),
    )
    db.add(record)
    await db.flush()
    return record


async def list_saifi_saidi_for_services(
    db: AsyncSession,
    *,
    service_ids: list[int],
    annee: int,
    mois: int,
) -> list[SaifiSaidi]:
    if not service_ids:
        return []
    result = await db.execute(
        select(SaifiSaidi).where(
            SaifiSaidi.service_id.in_(service_ids),
            SaifiSaidi.annee == annee,
            SaifiSaidi.mois == mois,
        )
    )
    return list(result.scalars().all())


async def list_service_ids_for_region(db: AsyncSession, region_id: int) -> list[int]:
    result = await db.execute(
        select(Service.id)
        .join(Agence, Service.agence_id == Agence.id)
        .join(Delegation, Agence.delegation_id == Delegation.id)
        .where(Delegation.region_id == region_id)
    )
    return list(result.scalars().all())


async def list_service_ids_for_delegation(db: AsyncSession, delegation_id: int) -> list[int]:
    result = await db.execute(
        select(Service.id)
        .join(Agence, Service.agence_id == Agence.id)
        .where(Agence.delegation_id == delegation_id)
    )
    return list(result.scalars().all())


async def list_all_service_ids(db: AsyncSession) -> list[int]:
    result = await db.execute(select(Service.id))
    return list(result.scalars().all())


async def get_region_id_for_service(db: AsyncSession, service_id: int) -> int | None:
    from app.repositories.end_repository import get_region_id_for_service as _get_region

    return await _get_region(db, service_id)
