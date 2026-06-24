"""Repository CRUD — réseau distribution (MT/BT)."""

from dataclasses import dataclass
from typing import Any, Type

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.repositories.geo_scope_repository import service_ids_in_region_subquery
from app.models.geo import Agence, Delegation, Service
from app.models.reseau import Feeder, Poste, PosteSource, SousFeeder, Troncon

ModelT = Type[Any]


@dataclass
class ScopeFilter:
    """Filtre RBAC lecture appliqué en couche repository."""

    service_id: int | None = None
    region_id: int | None = None


def _service_ids_in_region_subquery(region_id: int) -> Select[Any]:
    return service_ids_in_region_subquery(region_id)


def _apply_feeder_scope(query: Select[Any], scope: ScopeFilter | None) -> Select[Any]:
    if scope is None:
        return query
    if scope.service_id is not None:
        return query.where(Feeder.service_id == scope.service_id)
    if scope.region_id is not None:
        return query.where(Feeder.service_id.in_(_service_ids_in_region_subquery(scope.region_id)))
    return query


def _apply_feeder_join_scope(
    query: Select[Any], model: ModelT, scope: ScopeFilter | None
) -> Select[Any]:
    """Scope via jointure feeder pour troncons / sous_feeders."""
    if scope is None:
        return query
    query = query.join(Feeder, model.feeder_id == Feeder.id)
    if scope.service_id is not None:
        return query.where(Feeder.service_id == scope.service_id)
    if scope.region_id is not None:
        return query.where(Feeder.service_id.in_(_service_ids_in_region_subquery(scope.region_id)))
    return query


# ---------------------------------------------------------------------------
# Postes sources
# ---------------------------------------------------------------------------


async def list_postes_sources(
    db: AsyncSession,
    *,
    region_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[PosteSource]:
    query = select(PosteSource).where(PosteSource.is_active == True).order_by(PosteSource.id)
    if region_id is not None:
        query = query.where(PosteSource.region_id == region_id)
    if scope and scope.region_id is not None:
        query = query.where(PosteSource.region_id == scope.region_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_poste_source(db: AsyncSession, item_id: int) -> PosteSource | None:
    result = await db.execute(select(PosteSource).where(PosteSource.id == item_id))
    return result.scalar_one_or_none()


async def create_poste_source(db: AsyncSession, **values: Any) -> PosteSource:
    record = PosteSource(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_poste_source(db: AsyncSession, item_id: int, **values: Any) -> PosteSource | None:
    if values:
        await db.execute(
            update(PosteSource).where(PosteSource.id == item_id).values(**values)
        )
        await db.flush()
    return await get_poste_source(db, item_id)


# ---------------------------------------------------------------------------
# Feeders
# ---------------------------------------------------------------------------


async def list_feeders(
    db: AsyncSession,
    *,
    poste_source_id: int | None = None,
    service_id: int | None = None,
    region_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[Feeder]:
    query = (
        select(Feeder)
        .options(joinedload(Feeder.service), joinedload(Feeder.poste_source))
        .where(Feeder.is_active == True)
        .order_by(Feeder.id)
    )
    if region_id is not None:
        query = query.join(PosteSource, Feeder.poste_source_id == PosteSource.id).where(
            PosteSource.region_id == region_id
        )
    if poste_source_id is not None:
        query = query.where(Feeder.poste_source_id == poste_source_id)
    if service_id is not None:
        query = query.where(Feeder.service_id == service_id)
    query = _apply_feeder_scope(query, scope)
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def get_feeder(db: AsyncSession, item_id: int) -> Feeder | None:
    result = await db.execute(
        select(Feeder)
        .options(joinedload(Feeder.service), joinedload(Feeder.poste_source))
        .where(Feeder.id == item_id)
    )
    return result.unique().scalar_one_or_none()


async def get_feeder_by_code(db: AsyncSession, code: str) -> Feeder | None:
    result = await db.execute(select(Feeder).where(Feeder.code == code))
    return result.scalar_one_or_none()


async def create_feeder(db: AsyncSession, **values: Any) -> Feeder:
    record = Feeder(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_feeder(db: AsyncSession, item_id: int, **values: Any) -> Feeder | None:
    if values:
        await db.execute(update(Feeder).where(Feeder.id == item_id).values(**values))
        await db.flush()
    return await get_feeder(db, item_id)


# ---------------------------------------------------------------------------
# Postes
# ---------------------------------------------------------------------------


async def list_postes(
    db: AsyncSession,
    *,
    feeder_id: int | None = None,
    service_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[Poste]:
    query = select(Poste).where(Poste.is_active == True).order_by(Poste.id)
    if feeder_id is not None:
        query = query.where(Poste.feeder_id == feeder_id)
    if service_id is not None:
        query = query.where(Poste.service_id == service_id)
    if scope and scope.service_id is not None:
        query = query.where(Poste.service_id == scope.service_id)
    elif scope and scope.region_id is not None:
        query = query.where(Poste.service_id.in_(_service_ids_in_region_subquery(scope.region_id)))
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_poste(db: AsyncSession, item_id: int) -> Poste | None:
    result = await db.execute(select(Poste).where(Poste.id == item_id))
    return result.scalar_one_or_none()


async def create_poste(db: AsyncSession, **values: Any) -> Poste:
    record = Poste(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_poste(db: AsyncSession, item_id: int, **values: Any) -> Poste | None:
    if values:
        await db.execute(update(Poste).where(Poste.id == item_id).values(**values))
        await db.flush()
    return await get_poste(db, item_id)


# ---------------------------------------------------------------------------
# Tronçons
# ---------------------------------------------------------------------------


async def list_troncons(
    db: AsyncSession,
    *,
    feeder_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[Troncon]:
    query = select(Troncon).where(Troncon.is_active == True).order_by(Troncon.id)
    if feeder_id is not None:
        query = query.where(Troncon.feeder_id == feeder_id)
    if scope and (scope.service_id is not None or scope.region_id is not None):
        query = _apply_feeder_join_scope(query, Troncon, scope)
    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_troncon(db: AsyncSession, item_id: int) -> Troncon | None:
    result = await db.execute(select(Troncon).where(Troncon.id == item_id))
    return result.scalar_one_or_none()


async def create_troncon(db: AsyncSession, **values: Any) -> Troncon:
    record = Troncon(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_troncon(db: AsyncSession, item_id: int, **values: Any) -> Troncon | None:
    if values:
        await db.execute(update(Troncon).where(Troncon.id == item_id).values(**values))
        await db.flush()
    return await get_troncon(db, item_id)


# ---------------------------------------------------------------------------
# Sous-feeders
# ---------------------------------------------------------------------------


async def list_sous_feeders(
    db: AsyncSession,
    *,
    feeder_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[SousFeeder]:
    query = select(SousFeeder).where(SousFeeder.is_active == True).order_by(SousFeeder.id)
    if feeder_id is not None:
        query = query.where(SousFeeder.feeder_id == feeder_id)
    if scope and (scope.service_id is not None or scope.region_id is not None):
        query = _apply_feeder_join_scope(query, SousFeeder, scope)
    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_sous_feeder(db: AsyncSession, item_id: int) -> SousFeeder | None:
    result = await db.execute(select(SousFeeder).where(SousFeeder.id == item_id))
    return result.scalar_one_or_none()


async def create_sous_feeder(db: AsyncSession, **values: Any) -> SousFeeder:
    record = SousFeeder(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_sous_feeder(db: AsyncSession, item_id: int, **values: Any) -> SousFeeder | None:
    if values:
        await db.execute(update(SousFeeder).where(SousFeeder.id == item_id).values(**values))
        await db.flush()
    return await get_sous_feeder(db, item_id)
