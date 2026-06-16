"""Repository — interruptions réseau transport."""

from datetime import datetime
from typing import Any

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.interruptions import Interruption, InterruptionTransport
from app.schemas.common import PaginatedResponse
from app.utils.pagination import paginate

_TRANSPORT_TYPES = ("transport", "omvg")


def _base_transport_query():
    return (
        select(Interruption)
        .options(joinedload(Interruption.interruption_transport))
        .join(
            InterruptionTransport,
            InterruptionTransport.interruption_id == Interruption.id,
        )
        .where(Interruption.type_direction.in_(_TRANSPORT_TYPES))
    )


def _apply_filters(
    query,
    *,
    type_direction: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
    equipement_transport_id: int | None,
    source_transport_id: int | None,
):
    if type_direction is not None:
        query = query.where(Interruption.type_direction == type_direction)
    if statut is not None:
        query = query.where(Interruption.statut == statut)
    if date_debut is not None:
        query = query.where(Interruption.date_apparition >= date_debut)
    if date_fin is not None:
        query = query.where(Interruption.date_apparition <= date_fin)
    if equipement_transport_id is not None:
        query = query.where(
            InterruptionTransport.equipement_transport_id == equipement_transport_id
        )
    if source_transport_id is not None:
        query = query.where(
            InterruptionTransport.source_transport_id == source_transport_id
        )
    return query.order_by(Interruption.date_apparition.desc())


async def next_numero_interruption(
    db: AsyncSession,
    *,
    year: int,
    type_direction: str,
) -> int:
    """Numéro séquentiel pour interruptions transport/omvg sur l'année civile."""
    result = await db.execute(
        select(func.coalesce(func.max(Interruption.numero_interruption), 0)).where(
            Interruption.type_direction == type_direction,
            extract("year", Interruption.date_apparition) == year,
        )
    )
    return int(result.scalar_one()) + 1


async def get_interruption(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    result = await db.execute(
        select(Interruption)
        .options(joinedload(Interruption.interruption_transport))
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction.in_(_TRANSPORT_TYPES),
        )
    )
    return result.unique().scalar_one_or_none()


async def get_interruption_detail(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    """Charge une interruption transport/OMVG avec jointures pour la vue détail."""
    result = await db.execute(
        select(Interruption)
        .options(
            joinedload(Interruption.interruption_transport).joinedload(
                InterruptionTransport.equipement_transport
            ),
            joinedload(Interruption.interruption_transport).joinedload(
                InterruptionTransport.source_transport
            ),
            joinedload(Interruption.cause),
            joinedload(Interruption.nature),
            joinedload(Interruption.siege),
            joinedload(Interruption.signalisation),
            joinedload(Interruption.energie_nd),
            joinedload(Interruption.created_by),
            joinedload(Interruption.validated_by),
        )
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction.in_(_TRANSPORT_TYPES),
        )
    )
    return result.unique().scalar_one_or_none()


async def list_interruptions_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    type_direction: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    equipement_transport_id: int | None = None,
    source_transport_id: int | None = None,
) -> PaginatedResponse:
    query = _base_transport_query()
    query = _apply_filters(
        query,
        type_direction=type_direction,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        equipement_transport_id=equipement_transport_id,
        source_transport_id=source_transport_id,
    )
    return await paginate(db, query, page, page_size, scalar_type=Interruption)


async def create_interruption_transport(
    db: AsyncSession,
    *,
    interruption_values: dict[str, Any],
    transport_values: dict[str, Any],
) -> tuple[Interruption, InterruptionTransport]:
    interruption = Interruption(**interruption_values)
    db.add(interruption)
    await db.flush()

    transport = InterruptionTransport(
        interruption_id=interruption.id,
        **transport_values,
    )
    db.add(transport)
    await db.flush()
    await db.refresh(interruption)
    await db.refresh(transport)
    return interruption, transport


async def update_interruption_transport(
    db: AsyncSession,
    interruption_id: int,
    *,
    interruption_updates: dict[str, Any],
    transport_updates: dict[str, Any],
) -> tuple[Interruption, InterruptionTransport] | None:
    interruption = await get_interruption(db, interruption_id)
    if interruption is None or interruption.interruption_transport is None:
        return None

    transport = interruption.interruption_transport
    for key, value in interruption_updates.items():
        setattr(interruption, key, value)
    for key, value in transport_updates.items():
        setattr(transport, key, value)

    await db.flush()
    await db.refresh(interruption)
    await db.refresh(transport)
    return interruption, transport
