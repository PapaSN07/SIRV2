"""Service métier — réseau transport HTB (phase 2.4)."""

from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import reseau_transport_repository as repo
from app.schemas.common import PaginatedResponse
from app.schemas.reseau_transport import (
    READ_ROLES,
    VALID_SLUGS,
    EquipementTransportCreate,
    EquipementTransportResponse,
    EquipementTransportUpdate,
    PosteLigneCreate,
    PosteLigneResponse,
    PosteLigneUpdate,
    SourceTransportCreate,
    SourceTransportResponse,
    SourceTransportUpdate,
)
from app.utils.audit import ACTION_CREATE, ACTION_DELETE, ACTION_UPDATE, log_audit
from app.utils.pagination import clamp_page_size


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _validate_slug(slug: str) -> None:
    if slug not in VALID_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Ressource transport '{slug}' inconnue",
            },
        )


def _ensure_can_read(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if not _user_role_names(user).intersection(READ_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Accès lecture réseau transport non autorisé",
            },
        )


def _ensure_can_write(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if "ADMIN_DISPATCHING" not in _user_role_names(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Seul Admin Dispatching peut modifier le réseau transport",
            },
        )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"status": "error", "data": None, "error": "Élément introuvable"},
    )


def _conflict(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"status": "error", "data": None, "error": f"Code '{code}' déjà utilisé"},
    )


def _paginate_list(
    items: list[Any],
    page: int,
    page_size: int,
    builder: Callable[[Any], Any],
) -> PaginatedResponse[Any]:
    page = max(1, page)
    page_size = clamp_page_size(page_size)
    total = len(items)
    start = (page - 1) * page_size
    return PaginatedResponse(
        items=[builder(i) for i in items[start : start + page_size]],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_resources(
    db: AsyncSession,
    user: Utilisateur,
    slug: str,
    page: int,
    page_size: int,
    *,
    type_equipement: str | None = None,
    poste_source_id: int | None = None,
    equipement_transport_id: int | None = None,
) -> PaginatedResponse[Any]:
    _validate_slug(slug)
    _ensure_can_read(user)

    if slug == "equipements-transport":
        items = await repo.list_equipements(db, type_equipement=type_equipement)
        return _paginate_list(items, page, page_size, EquipementTransportResponse.model_validate)

    if slug == "sources-transport":
        items = await repo.list_sources(db)
        return _paginate_list(items, page, page_size, SourceTransportResponse.model_validate)

    items = await repo.list_postes_lignes(
        db,
        poste_source_id=poste_source_id,
        equipement_transport_id=equipement_transport_id,
    )
    return _paginate_list(items, page, page_size, PosteLigneResponse.model_validate)


async def get_resource(db: AsyncSession, user: Utilisateur, slug: str, item_id: int) -> Any:
    _validate_slug(slug)
    _ensure_can_read(user)

    if slug == "equipements-transport":
        record = await repo.get_equipement(db, item_id)
        if record is None:
            raise _not_found()
        return EquipementTransportResponse.model_validate(record)

    if slug == "sources-transport":
        record = await repo.get_source(db, item_id)
        if record is None:
            raise _not_found()
        return SourceTransportResponse.model_validate(record)

    record = await repo.get_poste_ligne(db, item_id)
    if record is None:
        raise _not_found()
    return PosteLigneResponse.model_validate(record)


async def create_resource(db: AsyncSession, user: Utilisateur, slug: str, body: Any) -> Any:
    _validate_slug(slug)
    _ensure_can_write(user)

    if slug == "equipements-transport":
        data = (
            body
            if isinstance(body, EquipementTransportCreate)
            else EquipementTransportCreate.model_validate(body)
        )
        if await repo.get_equipement_by_code(db, data.code):
            raise _conflict(data.code)
        record = await repo.create_equipement(db, **data.model_dump())
        resp = EquipementTransportResponse.model_validate(record)
        table = "equipements_transport"
    elif slug == "sources-transport":
        data = (
            body
            if isinstance(body, SourceTransportCreate)
            else SourceTransportCreate.model_validate(body)
        )
        if await repo.get_source_by_code(db, data.code):
            raise _conflict(data.code)
        record = await repo.create_source(db, **data.model_dump())
        resp = SourceTransportResponse.model_validate(record)
        table = "sources_transport"
    else:
        data = body if isinstance(body, PosteLigneCreate) else PosteLigneCreate.model_validate(body)
        record = await repo.create_poste_ligne(db, **data.model_dump())
        resp = PosteLigneResponse.model_validate(record)
        table = "postes_lignes"

    await log_audit(
        db,
        table_name=table,
        record_id=record.id,
        action=ACTION_CREATE,
        user_id=user.id,
        new_values={"id": record.id},
    )
    return resp


async def update_resource(
    db: AsyncSession,
    user: Utilisateur,
    slug: str,
    item_id: int,
    body: Any,
) -> Any:
    _validate_slug(slug)
    _ensure_can_write(user)
    await get_resource(db, user, slug, item_id)

    if slug == "equipements-transport":
        data = (
            body
            if isinstance(body, EquipementTransportUpdate)
            else EquipementTransportUpdate.model_validate(body)
        )
        record = await repo.update_equipement(db, item_id, **data.model_dump(exclude_unset=True))
        resp = EquipementTransportResponse.model_validate(record)
        table = "equipements_transport"
    elif slug == "sources-transport":
        data = (
            body
            if isinstance(body, SourceTransportUpdate)
            else SourceTransportUpdate.model_validate(body)
        )
        record = await repo.update_source(db, item_id, **data.model_dump(exclude_unset=True))
        resp = SourceTransportResponse.model_validate(record)
        table = "sources_transport"
    else:
        data = body if isinstance(body, PosteLigneUpdate) else PosteLigneUpdate.model_validate(body)
        record = await repo.update_poste_ligne(db, item_id, **data.model_dump(exclude_unset=True))
        resp = PosteLigneResponse.model_validate(record)
        table = "postes_lignes"

    if record is None:
        raise _not_found()

    await log_audit(
        db,
        table_name=table,
        record_id=item_id,
        action=ACTION_UPDATE,
        user_id=user.id,
        new_values=data.model_dump(exclude_unset=True),
    )
    return resp


async def delete_resource(
    db: AsyncSession,
    user: Utilisateur,
    slug: str,
    item_id: int,
) -> None:
    _validate_slug(slug)
    _ensure_can_write(user)
    await get_resource(db, user, slug, item_id)

    if slug == "equipements-transport":
        await repo.update_equipement(db, item_id, is_active=False)
        table = "equipements_transport"
    elif slug == "sources-transport":
        await repo.update_source(db, item_id, is_active=False)
        table = "sources_transport"
    else:
        await repo.update_poste_ligne(db, item_id, is_active=False)
        table = "postes_lignes"

    await log_audit(
        db,
        table_name=table,
        record_id=item_id,
        action=ACTION_DELETE,
        user_id=user.id,
        new_values={"is_active": False},
    )
