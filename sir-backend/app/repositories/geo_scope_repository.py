"""Helpers périmètre géographique — région d'un service (colonne services.region_id)."""

from __future__ import annotations

import asyncio

from sqlalchemy import Select, select
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import Agence, Delegation, Service


async def _close_result(result) -> None:
    close = getattr(result, "close", None)
    if close is not None:
        closed = close()
        if asyncio.iscoroutine(closed):
            await closed


def service_ids_in_region_subquery(region_id: int) -> Select:
    """Sous-requête des services rattachés à une région (colonne directe)."""
    return select(Service.id).where(Service.region_id == region_id)


async def _region_id_via_delegation(db: AsyncSession, service_id: int) -> int | None:
    result = await db.execute(
        select(Delegation.region_id)
        .join(Agence, Agence.delegation_id == Delegation.id)
        .join(Service, Service.agence_id == Agence.id)
        .where(Service.id == service_id)
    )
    region_id = result.scalar_one_or_none()
    await _close_result(result)
    return int(region_id) if region_id is not None else None


async def get_region_id_for_service(db: AsyncSession, service_id: int) -> int | None:
    """Région d'un service — colonne directe, repli hiérarchie agence/délégation."""
    try:
        result = await db.execute(select(Service.region_id).where(Service.id == service_id))
        region_id = result.scalar_one_or_none()
        await _close_result(result)
        if region_id is not None:
            return int(region_id)
    except (ProgrammingError, DBAPIError):
        pass

    return await _region_id_via_delegation(db, service_id)

async def service_in_region(
    db: AsyncSession,
    service_id: int,
    region_id: int,
) -> bool:
    resolved = await get_region_id_for_service(db, service_id)
    return resolved == region_id
