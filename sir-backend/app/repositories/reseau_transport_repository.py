"""Repository CRUD — réseau transport HTB."""

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reseau import EquipementTransport, PosteLigne, SourceTransport


async def list_equipements(
    db: AsyncSession,
    *,
    type_equipement: str | None = None,
) -> list[EquipementTransport]:
    query = (
        select(EquipementTransport)
        .where(EquipementTransport.is_active == True)  # noqa: E712
        .order_by(EquipementTransport.id)
    )
    if type_equipement is not None:
        query = query.where(EquipementTransport.type_equipement == type_equipement)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_equipement(db: AsyncSession, item_id: int) -> EquipementTransport | None:
    result = await db.execute(
        select(EquipementTransport).where(EquipementTransport.id == item_id)
    )
    return result.scalar_one_or_none()


async def get_equipement_by_code(db: AsyncSession, code: str) -> EquipementTransport | None:
    result = await db.execute(
        select(EquipementTransport).where(EquipementTransport.code == code)
    )
    return result.scalar_one_or_none()


async def create_equipement(db: AsyncSession, **values: Any) -> EquipementTransport:
    record = EquipementTransport(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_equipement(
    db: AsyncSession, item_id: int, **values: Any
) -> EquipementTransport | None:
    if values:
        await db.execute(
            update(EquipementTransport)
            .where(EquipementTransport.id == item_id)
            .values(**values)
        )
        await db.flush()
    return await get_equipement(db, item_id)


async def list_sources(db: AsyncSession) -> list[SourceTransport]:
    result = await db.execute(
        select(SourceTransport)
        .where(SourceTransport.is_active == True)  # noqa: E712
        .order_by(SourceTransport.id)
    )
    return list(result.scalars().all())


async def get_source(db: AsyncSession, item_id: int) -> SourceTransport | None:
    result = await db.execute(select(SourceTransport).where(SourceTransport.id == item_id))
    return result.scalar_one_or_none()


async def get_source_by_code(db: AsyncSession, code: str) -> SourceTransport | None:
    result = await db.execute(select(SourceTransport).where(SourceTransport.code == code))
    return result.scalar_one_or_none()


async def create_source(db: AsyncSession, **values: Any) -> SourceTransport:
    record = SourceTransport(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_source(db: AsyncSession, item_id: int, **values: Any) -> SourceTransport | None:
    if values:
        await db.execute(
            update(SourceTransport).where(SourceTransport.id == item_id).values(**values)
        )
        await db.flush()
    return await get_source(db, item_id)


async def list_postes_lignes(
    db: AsyncSession,
    *,
    poste_source_id: int | None = None,
    equipement_transport_id: int | None = None,
) -> list[PosteLigne]:
    query = select(PosteLigne).where(PosteLigne.is_active == True).order_by(PosteLigne.id)  # noqa: E712
    if poste_source_id is not None:
        query = query.where(PosteLigne.poste_source_id == poste_source_id)
    if equipement_transport_id is not None:
        query = query.where(PosteLigne.equipement_transport_id == equipement_transport_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_poste_ligne(db: AsyncSession, item_id: int) -> PosteLigne | None:
    result = await db.execute(select(PosteLigne).where(PosteLigne.id == item_id))
    return result.scalar_one_or_none()


async def create_poste_ligne(db: AsyncSession, **values: Any) -> PosteLigne:
    record = PosteLigne(**values, is_active=True)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update_poste_ligne(db: AsyncSession, item_id: int, **values: Any) -> PosteLigne | None:
    if values:
        await db.execute(update(PosteLigne).where(PosteLigne.id == item_id).values(**values))
        await db.flush()
    return await get_poste_ligne(db, item_id)
