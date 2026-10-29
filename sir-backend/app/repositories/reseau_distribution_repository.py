"""Repository CRUD — réseau distribution (MT/BT)."""

from dataclasses import dataclass
from typing import Any, Type

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.repositories.geo_scope_repository import service_ids_in_region_subquery
from app.models.interruptions import PosteInterruption
from app.models.reseau import Feeder, Poste, PosteSource, SousFeeder, Troncon

ModelT = Type[Any]


@dataclass
class ScopeFilter:
    """Filtre RBAC lecture appliqué en couche repository."""

    service_id: int | None = None
    region_id: int | None = None


def _service_ids_in_region_subquery(region_id: int) -> Select[Any]:
    return service_ids_in_region_subquery(region_id)


def _feeder_ids_in_region_subquery(region_id: int) -> Select[Any]:
    """Feeders d'une région : service dans la région, ou poste source rattaché à la région.

    Un feeder sans service (données migrées) reste ainsi visible via son poste source.
    """
    return (
        select(Feeder.id)
        .join(PosteSource, PosteSource.id == Feeder.poste_source_id)
        .where(
            or_(
                Feeder.service_id.in_(_service_ids_in_region_subquery(region_id)),
                PosteSource.region_id == region_id,
            )
        )
    )


def _apply_feeder_scope(query: Select[Any], scope: ScopeFilter | None) -> Select[Any]:
    if scope is None:
        return query
    if scope.service_id is not None:
        return query.where(Feeder.service_id == scope.service_id)
    if scope.region_id is not None:
        return query.where(Feeder.id.in_(_feeder_ids_in_region_subquery(scope.region_id)))
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
        return query.where(Feeder.id.in_(_feeder_ids_in_region_subquery(scope.region_id)))
    return query


# ---------------------------------------------------------------------------
# Postes sources
# ---------------------------------------------------------------------------


def _effective_region_id(region_id: int | None, scope: ScopeFilter | None) -> int | None:
    if region_id is not None:
        return region_id
    if scope and scope.region_id is not None:
        return scope.region_id
    return None


def _poste_source_ids_in_region_subquery(region_id: int) -> Select[Any]:
    """Postes sources rattachés à la région via au moins un feeder."""
    return (
        select(Feeder.poste_source_id)
        .where(
            Feeder.poste_source_id.isnot(None),
            Feeder.service_id.in_(_service_ids_in_region_subquery(region_id)),
        )
        .distinct()
    )


async def list_postes_sources(
    db: AsyncSession,
    *,
    region_id: int | None = None,
    scope: ScopeFilter | None = None,
) -> list[PosteSource]:
    query = select(PosteSource).where(PosteSource.is_active == True).order_by(PosteSource.libelle, PosteSource.id)  # noqa: E712
    effective_region = _effective_region_id(region_id, scope)
    if effective_region is not None:
        # La région du poste source fait foi ; les feeders ne servent qu'aux postes sources
        # sans région (données migrées). Sinon un poste source des Régions dont un feeder est
        # rattaché à un service de Dakar apparaissait dans la liste de Dakar.
        ps_in_region = _poste_source_ids_in_region_subquery(effective_region)
        query = query.where(
            or_(
                PosteSource.region_id == effective_region,
                and_(PosteSource.region_id.is_(None), PosteSource.id.in_(ps_in_region)),
            )
        )
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
        .where(Feeder.is_active == True)  # noqa: E712
        .order_by(Feeder.libelle, Feeder.id)
    )
    if region_id is not None:
        query = query.where(Feeder.id.in_(_feeder_ids_in_region_subquery(region_id)))
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
    query = select(Poste).where(Poste.is_active == True).order_by(Poste.libelle, Poste.id)  # noqa: E712
    if feeder_id is not None:
        # Postes rattachés au feeder, plus ceux sans feeder (migration) déjà impactés sur ce feeder
        historique = (
            select(PosteInterruption.poste_id)
            .where(PosteInterruption.feeder_id == feeder_id)
            .distinct()
        )
        query = query.where(
            or_(
                Poste.feeder_id == feeder_id,
                (Poste.feeder_id.is_(None)) & (Poste.id.in_(historique)),
            )
        )
    if service_id is not None:
        query = query.where(Poste.service_id == service_id)
    if scope and scope.service_id is not None:
        query = query.where(
            or_(
                Poste.service_id == scope.service_id,
                (Poste.service_id.is_(None))
                & Poste.feeder_id.in_(select(Feeder.id).where(Feeder.service_id == scope.service_id)),
            )
        )
    elif scope and scope.region_id is not None:
        region_feeders = _feeder_ids_in_region_subquery(scope.region_id)
        query = query.where(
            or_(
                Poste.service_id.in_(_service_ids_in_region_subquery(scope.region_id)),
                Poste.feeder_id.in_(region_feeders),
                (Poste.feeder_id.is_(None))
                & Poste.id.in_(
                    select(PosteInterruption.poste_id).where(
                        PosteInterruption.feeder_id.in_(region_feeders)
                    )
                ),
            )
        )
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
    query = select(Troncon).where(Troncon.is_active == True).order_by(Troncon.id)  # noqa: E712
    if feeder_id is not None:
        from app.repositories.sig_repository import _feeder_sig_nom_aliases

        feeder = await db.get(Feeder, feeder_id)
        feeder_ids = {feeder_id}
        if feeder is not None:
            for alias in _feeder_sig_nom_aliases(feeder):
                alias_upper = alias.upper()
                related = await db.execute(
                    select(Feeder.id).where(
                        or_(
                            func.upper(Feeder.libelle) == alias_upper,
                            func.upper(Feeder.code) == alias_upper,
                            func.upper(Feeder.libelle).like(func.concat(alias_upper, " %")),
                            func.upper(Feeder.code).like(func.concat(alias_upper, "_%")),
                        )
                    )
                )
                feeder_ids.update(int(r) for r in related.scalars().all())
        query = query.where(Troncon.feeder_id.in_(feeder_ids))
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
    query = select(SousFeeder).where(SousFeeder.is_active == True).order_by(SousFeeder.libelle, SousFeeder.id)  # noqa: E712
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
