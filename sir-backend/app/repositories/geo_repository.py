"""Repository lecture seule — hiérarchie géographique SENELEC."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Agence, Delegation, Region, Service


async def list_regions(db: AsyncSession, *, active_only: bool = True) -> list[Region]:
    query = select(Region).order_by(Region.id)
    if active_only:
        query = query.where(Region.is_active == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_region_by_id(db: AsyncSession, region_id: int) -> Region | None:
    result = await db.execute(select(Region).where(Region.id == region_id))
    return result.scalar_one_or_none()


async def list_delegations_by_region(
    db: AsyncSession,
    region_id: int,
    *,
    active_only: bool = True,
) -> list[Delegation]:
    query = select(Delegation).where(Delegation.region_id == region_id).order_by(Delegation.id)
    if active_only:
        query = query.where(Delegation.is_active == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_delegation_by_id(db: AsyncSession, delegation_id: int) -> Delegation | None:
    result = await db.execute(select(Delegation).where(Delegation.id == delegation_id))
    return result.scalar_one_or_none()


async def list_agences_by_delegation(
    db: AsyncSession,
    delegation_id: int,
    *,
    active_only: bool = True,
) -> list[Agence]:
    query = (
        select(Agence).where(Agence.delegation_id == delegation_id).order_by(Agence.id)
    )
    if active_only:
        query = query.where(Agence.is_active == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_agence_by_id(db: AsyncSession, agence_id: int) -> Agence | None:
    result = await db.execute(select(Agence).where(Agence.id == agence_id))
    return result.scalar_one_or_none()


async def list_services_by_agence(
    db: AsyncSession,
    agence_id: int,
    *,
    active_only: bool = True,
) -> list[Service]:
    query = select(Service).where(Service.agence_id == agence_id).order_by(Service.id)
    if active_only:
        query = query.where(Service.is_active == True)  # noqa: E712
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_services_by_region(
    db: AsyncSession,
    region_id: int,
    *,
    active_only: bool = True,
) -> list[Service]:
    query = (
        select(Service)
        .where(Service.region_id == region_id)
        .order_by(Service.libelle)
    )
    if active_only:
        query = query.where(Service.is_active == True)  # noqa: E712
    try:
        result = await db.execute(query)
        items = list(result.scalars().all())
        if items:
            return items
    except Exception:
        pass

    legacy_query = (
        select(Service)
        .join(Agence, Service.agence_id == Agence.id)
        .join(Delegation, Agence.delegation_id == Delegation.id)
        .where(Delegation.region_id == region_id)
        .order_by(Service.libelle)
    )
    if active_only:
        legacy_query = legacy_query.where(Service.is_active == True)  # noqa: E712
    result = await db.execute(legacy_query)
    return list(result.scalars().all())
