"""Service métier — référentiels partagés avec cache Redis (phase 2.1)."""

import json
from typing import Any

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.utilisateurs import Utilisateur
from app.repositories import referentiel_repository as ref_repo
from app.schemas.common import PaginatedResponse
from app.schemas.referentiel import (
    READ_ONLY_RESOURCES,
    RESOURCES_WITH_TYPE_RESEAU,
    SCR_ONLY_RESOURCES,
    VALID_RESOURCES,
    ReferentielCreate,
    ReferentielResponse,
    ReferentielUpdate,
)
from app.utils.audit import ACTION_CREATE, ACTION_DELETE, ACTION_UPDATE, log_audit
from app.utils.pagination import paginate

_CACHE_TTL_SECONDS = 86400  # 24h
_VERSION_KEY = "referentiel:{resource}:version"


def _validate_resource(resource: str) -> None:
    if resource not in VALID_RESOURCES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Ressource '{resource}' inconnue",
            },
        )


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _ensure_can_write(
    user: Utilisateur,
    resource: str,
    type_reseau: str | None,
) -> None:
    """Admin SCR → distribution/commun · Admin Dispatching → transport/commun."""
    if resource in READ_ONLY_RESOURCES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": f"Le référentiel '{resource}' est en lecture seule",
            },
        )
    if is_superadmin(user):
        return
    roles = _user_role_names(user)

    if resource in SCR_ONLY_RESOURCES and "ADMIN_SCR" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": f"Seul Admin SCR peut modifier '{resource}'",
            },
        )

    if not roles.intersection({"ADMIN_SCR", "ADMIN_DISPATCHING"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Seuls Admin SCR et Admin Dispatching peuvent modifier les référentiels",
            },
        )

    if "ADMIN_SAQS" in roles and not roles.intersection({"ADMIN_SCR", "ADMIN_DISPATCHING"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Admin SAQS : lecture seule",
            },
        )

    # natures et types_end : les deux admins peuvent gérer
    if resource not in RESOURCES_WITH_TYPE_RESEAU:
        return

    if type_reseau is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": f"type_reseau obligatoire pour '{resource}'",
            },
        )

    if "ADMIN_SCR" in roles and type_reseau in ("distribution", "commun"):
        return
    if "ADMIN_DISPATCHING" in roles and type_reseau in ("transport", "commun"):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": f"type_reseau '{type_reseau}' hors périmètre de votre direction",
        },
    )


def _build_response(record: Any) -> ReferentielResponse:
    return ReferentielResponse(
        id=record.id,
        code=record.code,
        libelle=record.libelle,
        type_reseau=getattr(record, "type_reseau", None),
        description=getattr(record, "description", None),
        is_active=getattr(record, "is_active", True),
    )


def _cache_key(
    resource: str,
    version: int,
    type_reseau: str | None,
    page: int,
    page_size: int,
) -> str:
    tr = type_reseau or "all"
    return f"referentiel:{resource}:v{version}:{tr}:{page}:{page_size}"


async def _get_cache_version(redis: Redis, resource: str) -> int:
    raw = await redis.get(_VERSION_KEY.format(resource=resource))
    return int(raw) if raw else 0


async def _invalidate_cache(redis: Redis, resource: str) -> None:
    await redis.incr(_VERSION_KEY.format(resource=resource))


async def list_items(
    db: AsyncSession,
    redis: Redis,
    resource: str,
    page: int,
    page_size: int,
    type_reseau: str | None = None,
) -> PaginatedResponse[ReferentielResponse]:
    _validate_resource(resource)

    version = await _get_cache_version(redis, resource)
    key = _cache_key(resource, version, type_reseau, page, page_size)

    cached = await redis.get(key)
    if cached:
        data = json.loads(cached)
        items = [ReferentielResponse(**item) for item in data["items"]]
        return PaginatedResponse(
            items=items,
            total=data["total"],
            page=data["page"],
            page_size=data["page_size"],
        )

    query = ref_repo.build_select_query(resource, type_reseau=type_reseau)
    model = ref_repo.get_model(resource)
    result = await paginate(db, query, page, page_size, scalar_type=model)
    items = [_build_response(r) for r in result.items]

    paginated = PaginatedResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )

    await redis.setex(
        key,
        _CACHE_TTL_SECONDS,
        json.dumps(
            {
                "items": [i.model_dump() for i in items],
                "total": paginated.total,
                "page": paginated.page,
                "page_size": paginated.page_size,
            },
            ensure_ascii=False,
        ),
    )

    return paginated


async def get_item(
    db: AsyncSession,
    resource: str,
    item_id: int,
) -> ReferentielResponse:
    _validate_resource(resource)
    record = await ref_repo.get_by_id(db, resource, item_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Élément référentiel introuvable",
            },
        )
    return _build_response(record)


async def create_item(
    db: AsyncSession,
    redis: Redis,
    current_user: Utilisateur,
    resource: str,
    body: ReferentielCreate,
) -> ReferentielResponse:
    _validate_resource(resource)
    _ensure_can_write(current_user, resource, body.type_reseau)

    existing = await ref_repo.get_by_code(db, resource, body.code)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "error",
                "data": None,
                "error": f"Le code '{body.code}' existe déjà pour '{resource}'",
            },
        )

    record = await ref_repo.create(
        db,
        resource,
        code=body.code,
        libelle=body.libelle,
        type_reseau=body.type_reseau,
        description=body.description,
    )

    await log_audit(
        db,
        table_name=resource,
        record_id=record.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={"code": record.code, "libelle": record.libelle},
    )

    await _invalidate_cache(redis, resource)
    return _build_response(record)


async def update_item(
    db: AsyncSession,
    redis: Redis,
    current_user: Utilisateur,
    resource: str,
    item_id: int,
    body: ReferentielUpdate,
) -> ReferentielResponse:
    _validate_resource(resource)

    record = await ref_repo.get_by_id(db, resource, item_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Élément référentiel introuvable",
            },
        )

    effective_type = body.type_reseau or getattr(record, "type_reseau", None)
    _ensure_can_write(current_user, resource, effective_type)

    if body.code and body.code != record.code:
        duplicate = await ref_repo.get_by_code(db, resource, body.code)
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Le code '{body.code}' existe déjà",
                },
            )

    old_values = {"code": record.code, "libelle": record.libelle}
    updated = await ref_repo.update(
        db,
        resource,
        item_id,
        code=body.code,
        libelle=body.libelle,
        type_reseau=body.type_reseau,
        description=body.description,
        is_active=body.is_active,
    )
    assert updated is not None

    await log_audit(
        db,
        table_name=resource,
        record_id=item_id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={"code": updated.code, "libelle": updated.libelle},
    )

    await _invalidate_cache(redis, resource)
    return _build_response(updated)


async def delete_item(
    db: AsyncSession,
    redis: Redis,
    current_user: Utilisateur,
    resource: str,
    item_id: int,
) -> None:
    _validate_resource(resource)

    record = await ref_repo.get_by_id(db, resource, item_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Élément référentiel introuvable",
            },
        )

    type_reseau = getattr(record, "type_reseau", None)
    _ensure_can_write(current_user, resource, type_reseau)

    await ref_repo.soft_delete(db, resource, item_id)

    await log_audit(
        db,
        table_name=resource,
        record_id=item_id,
        action=ACTION_DELETE,
        user_id=current_user.id,
        old_values={"code": record.code, "is_active": True},
        new_values={"is_active": False},
    )

    await _invalidate_cache(redis, resource)
