"""Repository générique CRUD pour les tables référentielles."""

from typing import Any, Type

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.referentiel import (
    Cause,
    DirectionSource,
    Entreprise,
    Nature,
    Prestataire,
    Siege,
    Signalisation,
    Statut,
    TypeEnd,
    TypeReseau,
)
from app.schemas.referentiel import RESOURCES_WITH_TYPE_RESEAU, VALID_RESOURCES

ResourceModel = Type[Any]

RESOURCE_MODELS: dict[str, ResourceModel] = {
    "causes": Cause,
    "sieges": Siege,
    "signalisations": Signalisation,
    "natures": Nature,
    "types_end": TypeEnd,
    "types_reseaux": TypeReseau,
    "entreprises": Entreprise,
    "prestataires": Prestataire,
    "statuts": Statut,
    "direction_sources": DirectionSource,
}


def get_model(resource: str) -> ResourceModel:
    if resource not in VALID_RESOURCES:
        raise ValueError(f"Ressource '{resource}' invalide")
    return RESOURCE_MODELS[resource]


def _to_dict(record: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": record.id,
        "code": record.code,
        "libelle": record.libelle,
        "is_active": getattr(record, "is_active", True),
    }
    if hasattr(record, "type_reseau"):
        data["type_reseau"] = record.type_reseau
    if hasattr(record, "description"):
        data["description"] = record.description
    return data


def build_select_query(
    resource: str,
    *,
    type_reseau: str | None = None,
    active_only: bool = True,
) -> Select[Any]:
    model = get_model(resource)
    query = select(model)
    if active_only and hasattr(model, "is_active"):
        query = query.where(model.is_active == True)
    if type_reseau and resource in RESOURCES_WITH_TYPE_RESEAU:
        query = query.where(model.type_reseau == type_reseau)
    if hasattr(model, "ordre"):
        return query.order_by(model.ordre)
    return query.order_by(model.id)


async def get_by_id(
    db: AsyncSession,
    resource: str,
    item_id: int,
) -> Any | None:
    model = get_model(resource)
    result = await db.execute(select(model).where(model.id == item_id))
    return result.scalar_one_or_none()


async def get_by_code(
    db: AsyncSession,
    resource: str,
    code: str,
) -> Any | None:
    model = get_model(resource)
    result = await db.execute(select(model).where(model.code == code))
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    resource: str,
    *,
    code: str,
    libelle: str,
    type_reseau: str | None = None,
    description: str | None = None,
) -> Any:
    model = get_model(resource)
    values: dict[str, Any] = {
        "code": code,
        "libelle": libelle,
        "is_active": True,
    }
    if resource in RESOURCES_WITH_TYPE_RESEAU:
        values["type_reseau"] = type_reseau
    if resource == "types_end" and description is not None:
        values["description"] = description

    record = model(**values)
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record


async def update(
    db: AsyncSession,
    resource: str,
    item_id: int,
    *,
    code: str | None = None,
    libelle: str | None = None,
    type_reseau: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
) -> Any | None:
    record = await get_by_id(db, resource, item_id)
    if record is None:
        return None

    values: dict[str, Any] = {}
    if code is not None:
        values["code"] = code
    if libelle is not None:
        values["libelle"] = libelle
    if type_reseau is not None and resource in RESOURCES_WITH_TYPE_RESEAU:
        values["type_reseau"] = type_reseau
    if description is not None and resource == "types_end":
        values["description"] = description
    if is_active is not None:
        values["is_active"] = is_active

    if values:
        model = get_model(resource)
        await db.execute(update(model).where(model.id == item_id).values(**values))
        await db.flush()

    return await get_by_id(db, resource, item_id)


async def soft_delete(db: AsyncSession, resource: str, item_id: int) -> Any | None:
    return await update(db, resource, item_id, is_active=False)
