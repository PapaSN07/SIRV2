"""Repository — interruptions réseau distribution."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.repositories.geo_scope_repository import (
    service_ids_in_region_subquery,
    service_in_region as _service_in_region,
)
from app.models.geo import Agence, Delegation, Service
from app.models.interruptions import Interruption, InterruptionDistribution, PosteInterruption
from app.models.reseau import Poste
from app.repositories.reseau_distribution_repository import ScopeFilter
from app.schemas.common import PaginatedResponse
from app.utils.pagination import paginate


def _service_ids_in_region_subquery(region_id: int):
    return service_ids_in_region_subquery(region_id)


def _base_distribution_query():
    return (
        select(Interruption)
        .options(
            joinedload(Interruption.interruption_distribution),
            joinedload(Interruption.cause),
            joinedload(Interruption.nature),
            joinedload(Interruption.siege),
            joinedload(Interruption.feeder),
            joinedload(Interruption.poste_source),
            joinedload(Interruption.service)
            .joinedload(Service.agence)
            .joinedload(Agence.delegation)
            .joinedload(Delegation.region),
        )
        .join(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(Interruption.type_direction == "distribution")
    )


def _apply_list_filters(
    query,
    *,
    region_id: int | None,
    service_id: int | None,
    feeder_id: int | None,
    nature_id: int | None,
    ouverture: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
    with_order: bool = True,
):
    if region_id is not None:
        query = query.where(
            Interruption.service_id.in_(_service_ids_in_region_subquery(region_id))
        )
    if service_id is not None:
        query = query.where(Interruption.service_id == service_id)
    if feeder_id is not None:
        query = query.where(Interruption.feeder_id == feeder_id)
    if nature_id is not None:
        query = query.where(Interruption.nature_id == nature_id)
    if ouverture == "ouvert":
        query = query.where(Interruption.statut == "en_cours")
    elif ouverture == "ferme":
        query = query.where(Interruption.statut.in_(("cloture", "valide", "archive")))
    elif statut is not None:
        query = query.where(Interruption.statut == statut)
    if date_debut is not None:
        query = query.where(Interruption.date_apparition >= date_debut)
    if date_fin is not None:
        query = query.where(Interruption.date_apparition <= date_fin)
    if with_order:
        return query.order_by(Interruption.date_apparition.desc())
    return query


def _apply_scope(query, scope: ScopeFilter | None):
    if scope is None:
        return query
    if scope.service_id is not None:
        return query.where(Interruption.service_id == scope.service_id)
    if scope.region_id is not None:
        return query.where(
            Interruption.service_id.in_(_service_ids_in_region_subquery(scope.region_id))
        )
    return query


def _apply_filters(
    query,
    *,
    region_id: int | None,
    service_id: int | None,
    feeder_id: int | None,
    nature_id: int | None,
    ouverture: str | None,
    statut: str | None,
    date_debut: datetime | None,
    date_fin: datetime | None,
):
    return _apply_list_filters(
        query,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )


async def next_numero_interruption(
    db: AsyncSession,
    *,
    year: int,
) -> int:
    """Numéro séquentiel pour les interruptions distribution sur l'année civile."""
    result = await db.execute(
        select(func.coalesce(func.max(Interruption.numero_interruption), 0)).where(
            Interruption.type_direction == "distribution",
            extract("year", Interruption.date_apparition) == year,
        )
    )
    current_max = result.scalar_one()
    return int(current_max) + 1


async def get_interruption(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    result = await db.execute(
        select(Interruption)
        .options(joinedload(Interruption.interruption_distribution))
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction == "distribution",
        )
    )
    return result.unique().scalar_one_or_none()


async def get_interruption_for_response(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    """Charge une interruption avec jointures pour InterruptionDistributionResponse."""
    result = await db.execute(
        select(Interruption)
        .options(
            joinedload(Interruption.interruption_distribution),
            joinedload(Interruption.cause),
            joinedload(Interruption.nature),
            joinedload(Interruption.siege),
            joinedload(Interruption.feeder),
            joinedload(Interruption.poste_source),
            joinedload(Interruption.service)
            .joinedload(Service.agence)
            .joinedload(Agence.delegation)
            .joinedload(Delegation.region),
        )
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction == "distribution",
        )
    )
    return result.unique().scalar_one_or_none()


async def get_interruption_detail(
    db: AsyncSession,
    interruption_id: int,
) -> Interruption | None:
    """Charge une interruption distribution avec jointures pour la vue détail."""
    result = await db.execute(
        select(Interruption)
        .options(
            joinedload(Interruption.interruption_distribution),
            joinedload(Interruption.feeder),
            joinedload(Interruption.poste_source),
            joinedload(Interruption.cause),
            joinedload(Interruption.nature),
            joinedload(Interruption.siege),
            joinedload(Interruption.signalisation),
            joinedload(Interruption.service)
            .joinedload(Service.agence)
            .joinedload(Agence.delegation)
            .joinedload(Delegation.region),
            joinedload(Interruption.postes_interrompus).joinedload(PosteInterruption.poste),
            joinedload(Interruption.energie_nd),
            joinedload(Interruption.created_by),
            joinedload(Interruption.validated_by),
        )
        .where(
            Interruption.id == interruption_id,
            Interruption.type_direction == "distribution",
        )
    )
    return result.unique().scalar_one_or_none()


async def service_in_region(
    db: AsyncSession,
    service_id: int,
    region_id: int,
) -> bool:
    return await _service_in_region(db, service_id, region_id)


async def create_interruption_distribution(
    db: AsyncSession,
    *,
    interruption_values: dict[str, Any],
    distribution_values: dict[str, Any],
) -> tuple[Interruption, InterruptionDistribution]:
    interruption = Interruption(**interruption_values)
    db.add(interruption)
    await db.flush()

    distribution = InterruptionDistribution(
        interruption_id=interruption.id,
        **distribution_values,
    )
    db.add(distribution)
    await db.flush()
    await db.refresh(interruption)
    await db.refresh(distribution)
    return interruption, distribution


async def list_interruptions_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    scope: ScopeFilter | None = None,
    region_id: int | None = None,
    service_id: int | None = None,
    feeder_id: int | None = None,
    nature_id: int | None = None,
    ouverture: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse:
    query = _base_distribution_query()
    query = _apply_scope(query, scope)
    query = _apply_filters(
        query,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return await paginate(db, query, page, page_size, scalar_type=Interruption)


async def count_interruptions_scoped(
    db: AsyncSession,
    *,
    scope: ScopeFilter | None = None,
    region_id: int | None = None,
    service_id: int | None = None,
    feeder_id: int | None = None,
    nature_id: int | None = None,
    ouverture: str | None = None,
    statut: str | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    non_validees_only: bool = False,
) -> int:
    query = (
        select(func.count())
        .select_from(Interruption)
        .join(
            InterruptionDistribution,
            InterruptionDistribution.interruption_id == Interruption.id,
        )
        .where(Interruption.type_direction == "distribution")
    )
    query = _apply_scope(query, scope)
    query = _apply_list_filters(
        query,
        region_id=region_id,
        service_id=service_id,
        feeder_id=feeder_id,
        nature_id=nature_id,
        ouverture=ouverture,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        with_order=False,
    )
    if non_validees_only:
        query = query.where(Interruption.statut.in_(("en_cours", "cloture")))
    result = await db.execute(query)
    return int(result.scalar_one())


async def count_postes_for_interruption(db: AsyncSession, interruption_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(PosteInterruption)
        .where(PosteInterruption.interruption_id == interruption_id)
    )
    return int(result.scalar_one())


async def list_postes_for_interruption(
    db: AsyncSession,
    interruption_id: int,
) -> list[PosteInterruption]:
    result = await db.execute(
        select(PosteInterruption)
        .options(joinedload(PosteInterruption.poste))
        .where(PosteInterruption.interruption_id == interruption_id)
        .order_by(PosteInterruption.id)
    )
    return list(result.scalars().unique().all())


async def list_linked_poste_ids(db: AsyncSession, interruption_id: int) -> set[int]:
    result = await db.execute(
        select(PosteInterruption.poste_id).where(
            PosteInterruption.interruption_id == interruption_id
        )
    )
    return {int(row[0]) for row in result.all()}


async def get_poste_interruption_link(
    db: AsyncSession,
    interruption_id: int,
    poste_id: int,
) -> PosteInterruption | None:
    result = await db.execute(
        select(PosteInterruption).where(
            PosteInterruption.interruption_id == interruption_id,
            PosteInterruption.poste_id == poste_id,
        )
    )
    return result.scalar_one_or_none()


async def add_poste_interruption(
    db: AsyncSession,
    *,
    interruption_id: int,
    poste_id: int,
    nombre_clients_touches: int | None,
) -> PosteInterruption:
    link = PosteInterruption(
        interruption_id=interruption_id,
        poste_id=poste_id,
        nombre_clients_touches=nombre_clients_touches,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link


async def delete_poste_interruption(
    db: AsyncSession,
    interruption_id: int,
    poste_id: int,
) -> bool:
    link = await get_poste_interruption_link(db, interruption_id, poste_id)
    if link is None:
        return False
    await db.execute(
        delete(PosteInterruption).where(
            PosteInterruption.interruption_id == interruption_id,
            PosteInterruption.poste_id == poste_id,
        )
    )
    await db.flush()
    return True


async def update_interruption_distribution(
    db: AsyncSession,
    interruption_id: int,
    *,
    interruption_updates: dict[str, Any],
    distribution_updates: dict[str, Any],
) -> tuple[Interruption, InterruptionDistribution] | None:
    interruption = await get_interruption(db, interruption_id)
    if interruption is None or interruption.interruption_distribution is None:
        return None

    distribution = interruption.interruption_distribution
    for key, value in interruption_updates.items():
        setattr(interruption, key, value)
    for key, value in distribution_updates.items():
        setattr(distribution, key, value)

    await db.flush()
    await db.refresh(interruption)
    await db.refresh(distribution)
    return interruption, distribution
