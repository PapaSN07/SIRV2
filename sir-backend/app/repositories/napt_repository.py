"""Repository — NAPT et consignations."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.geo import Service
from app.models.napt import Consignation, Napt
from app.models.reseau import Feeder
from app.schemas.common import PaginatedResponse
from app.utils.pagination import paginate


def _base_napt_query():
    return (
        select(Napt)
        .options(
            joinedload(Napt.service),
            joinedload(Napt.feeder),
            selectinload(Napt.consignations),
        )
        .order_by(Napt.created_at.desc())
    )


async def next_numero_napt(db: AsyncSession, year: int) -> str:
    prefix = f"NAPT-{year}-"
    result = await db.execute(
        select(func.count()).select_from(Napt).where(Napt.numero_napt.like(f"{prefix}%"))
    )
    seq = int(result.scalar_one()) + 1
    return f"{prefix}{seq:04d}"


async def list_napt_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    service_id: int | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse:
    query = _base_napt_query()
    if service_id is not None:
        query = query.where(Napt.service_id == service_id)
    if statut is not None:
        query = query.where(Napt.statut == statut)
    if date_debut is not None:
        query = query.where(Napt.date_debut_prevue >= date_debut)
    if date_fin is not None:
        query = query.where(Napt.date_debut_prevue <= date_fin)
    return await paginate(db, query, page, page_size, scalar_type=Napt)


async def get_napt(db: AsyncSession, napt_id: int) -> Napt | None:
    result = await db.execute(
        _base_napt_query().where(Napt.id == napt_id)
    )
    return result.unique().scalar_one_or_none()


async def create_napt(db: AsyncSession, values: dict) -> Napt:
    napt = Napt(**values)
    db.add(napt)
    await db.flush()
    await db.refresh(napt)
    return napt


async def update_napt(db: AsyncSession, napt: Napt, values: dict) -> Napt:
    for key, value in values.items():
        setattr(napt, key, value)
    await db.flush()
    await db.refresh(napt)
    return napt


async def create_consignation(db: AsyncSession, values: dict) -> Consignation:
    cons = Consignation(**values)
    db.add(cons)
    await db.flush()
    await db.refresh(cons)
    return cons


async def get_consignation(db: AsyncSession, consignation_id: int) -> Consignation | None:
    result = await db.execute(select(Consignation).where(Consignation.id == consignation_id))
    return result.scalar_one_or_none()


async def get_service(db: AsyncSession, service_id: int) -> Service | None:
    result = await db.execute(select(Service).where(Service.id == service_id))
    return result.scalar_one_or_none()


async def get_feeder(db: AsyncSession, feeder_id: int) -> Feeder | None:
    result = await db.execute(select(Feeder).where(Feeder.id == feeder_id))
    return result.scalar_one_or_none()
