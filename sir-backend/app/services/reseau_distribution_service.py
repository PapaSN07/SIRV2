"""Service métier — réseau distribution MT/BT (phase 2.3)."""

from typing import Any, Callable

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import is_superadmin
from app.models.reseau import Feeder, Poste, PosteSource, SousFeeder, Troncon
from app.models.utilisateurs import Utilisateur
from app.repositories import reseau_distribution_repository as repo
from app.repositories.reseau_distribution_repository import ScopeFilter
from app.schemas.common import PaginatedResponse
from app.schemas.reseau_distribution import (
    READ_ROLES,
    VALID_SLUGS,
    FeederCreate,
    FeederResponse,
    FeederUpdate,
    PosteCreate,
    PosteResponse,
    PosteSourceCreate,
    PosteSourceResponse,
    PosteSourceUpdate,
    PosteUpdate,
    SousFeederCreate,
    SousFeederResponse,
    SousFeederUpdate,
    TronconCreate,
    TronconResponse,
    TronconUpdate,
)
from app.utils.audit import ACTION_CREATE, ACTION_DELETE, ACTION_UPDATE, log_audit
from app.utils.pagination import clamp_page_size


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _feeder_response(record: Feeder) -> FeederResponse:
    base = FeederResponse.model_validate(record)
    return base.model_copy(
        update={
            "service_libelle": record.service.libelle if record.service else None,
            "poste_source_libelle": record.poste_source.libelle
            if record.poste_source
            else None,
        }
    )


def _validate_slug(slug: str) -> None:
    if slug not in VALID_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Ressource réseau '{slug}' inconnue",
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
                "error": "Accès lecture réseau distribution non autorisé",
            },
        )


def _ensure_can_write(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if "ADMIN_SCR" not in _user_role_names(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Seul Admin SCR peut modifier le réseau distribution",
            },
        )


def _read_scope(user: Utilisateur) -> ScopeFilter | None:
    if is_superadmin(user):
        return None
    roles = _user_role_names(user)
    if roles.intersection({"ADMIN_SCR", "ADMIN_SAQS"}):
        return None
    if roles.intersection({"BCC", "BRC"}):
        region_id = user.user_roles[0].scope_service_id
        if region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre régional non configuré pour ce compte",
                },
            )
        return ScopeFilter(region_id=region_id)
    if "SUPERVISEUR" in roles:
        return ScopeFilter(service_id=user.user_roles[0].scope_service_id)
    return None


def _paginate_list(
    items: list[Any],
    page: int,
    page_size: int,
    response_builder: Callable[[Any], Any],
) -> PaginatedResponse[Any]:
    page = max(1, page)
    page_size = clamp_page_size(page_size)
    total = len(items)
    start = (page - 1) * page_size
    page_items = [response_builder(i) for i in items[start : start + page_size]]
    return PaginatedResponse(items=page_items, total=total, page=page, page_size=page_size)


def _check_poste_source_scope(user: Utilisateur, record: PosteSource) -> None:
    scope = _read_scope(user)
    if scope and scope.region_id is not None and record.region_id != scope.region_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Hors périmètre régional"},
        )


def _check_feeder_scope(user: Utilisateur, record: Feeder) -> None:
    scope = _read_scope(user)
    if scope is None:
        return
    if scope.service_id is not None and record.service_id != scope.service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Hors périmètre service"},
        )
    if scope.region_id is not None:
        svc_region = record.service.region_id if record.service is not None else None
        if svc_region != scope.region_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "data": None, "error": "Hors périmètre régional"},
            )


def _check_poste_scope(user: Utilisateur, record: Poste) -> None:
    scope = _read_scope(user)
    if scope and scope.service_id is not None and record.service_id != scope.service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "data": None, "error": "Hors périmètre service"},
        )


# ---------------------------------------------------------------------------
# List / Get dispatchers
# ---------------------------------------------------------------------------


async def list_resources(
    db: AsyncSession,
    user: Utilisateur,
    slug: str,
    page: int,
    page_size: int,
    *,
    region_id: int | None = None,
    poste_source_id: int | None = None,
    service_id: int | None = None,
    feeder_id: int | None = None,
) -> PaginatedResponse[Any]:
    _validate_slug(slug)
    _ensure_can_read(user)
    scope = _read_scope(user)

    if slug == "postes-sources":
        items = await repo.list_postes_sources(db, region_id=region_id, scope=scope)
        return _paginate_list(items, page, page_size, PosteSourceResponse.model_validate)

    if slug == "feeders":
        items = await repo.list_feeders(
            db,
            poste_source_id=poste_source_id,
            service_id=service_id,
            region_id=region_id,
            scope=scope,
        )
        return _paginate_list(items, page, page_size, _feeder_response)

    if slug == "postes":
        items = await repo.list_postes(
            db, feeder_id=feeder_id, service_id=service_id, scope=scope
        )
        return _paginate_list(items, page, page_size, PosteResponse.model_validate)

    if slug == "troncons":
        items = await repo.list_troncons(db, feeder_id=feeder_id, scope=scope)
        return _paginate_list(items, page, page_size, TronconResponse.model_validate)

    items = await repo.list_sous_feeders(db, feeder_id=feeder_id, scope=scope)
    return _paginate_list(items, page, page_size, SousFeederResponse.model_validate)


async def get_resource(db: AsyncSession, user: Utilisateur, slug: str, item_id: int) -> Any:
    _validate_slug(slug)
    _ensure_can_read(user)

    if slug == "postes-sources":
        record = await repo.get_poste_source(db, item_id)
        if record is None:
            raise _not_found()
        _check_poste_source_scope(user, record)
        return PosteSourceResponse.model_validate(record)

    if slug == "feeders":
        record = await repo.get_feeder(db, item_id)
        if record is None:
            raise _not_found()
        _check_feeder_scope(user, record)
        return _feeder_response(record)

    if slug == "postes":
        record = await repo.get_poste(db, item_id)
        if record is None:
            raise _not_found()
        _check_poste_scope(user, record)
        return PosteResponse.model_validate(record)

    if slug == "troncons":
        record = await repo.get_troncon(db, item_id)
        if record is None:
            raise _not_found()
        if record.feeder_id:
            feeder = await repo.get_feeder(db, record.feeder_id)
            if feeder:
                _check_feeder_scope(user, feeder)
        return TronconResponse.model_validate(record)

    record = await repo.get_sous_feeder(db, item_id)
    if record is None:
        raise _not_found()
    feeder = await repo.get_feeder(db, record.feeder_id)
    if feeder:
        _check_feeder_scope(user, feeder)
    return SousFeederResponse.model_validate(record)


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"status": "error", "data": None, "error": "Élément introuvable"},
    )


# ---------------------------------------------------------------------------
# Create / Update / Delete
# ---------------------------------------------------------------------------


async def create_resource(
    db: AsyncSession,
    user: Utilisateur,
    slug: str,
    body: Any,
) -> Any:
    _validate_slug(slug)
    _ensure_can_write(user)

    if slug == "postes-sources":
        data = body if isinstance(body, PosteSourceCreate) else PosteSourceCreate.model_validate(body)
        record = await repo.create_poste_source(
            db,
            code=data.code,
            libelle=data.libelle,
            region_id=data.region_id,
            puissance_mva=data.puissance_mva,
        )
        resp = PosteSourceResponse.model_validate(record)
        table = "postes_sources"
    elif slug == "feeders":
        data = body if isinstance(body, FeederCreate) else FeederCreate.model_validate(body)
        existing = await repo.get_feeder_by_code(db, data.code)
        if existing:
            raise _conflict(data.code)
        record = await repo.create_feeder(db, **data.model_dump())
        resp = FeederResponse.model_validate(record)
        table = "feeders"
    elif slug == "postes":
        data = body if isinstance(body, PosteCreate) else PosteCreate.model_validate(body)
        record = await repo.create_poste(db, **data.model_dump())
        resp = PosteResponse.model_validate(record)
        table = "postes"
    elif slug == "troncons":
        data = body if isinstance(body, TronconCreate) else TronconCreate.model_validate(body)
        record = await repo.create_troncon(db, **data.model_dump())
        resp = TronconResponse.model_validate(record)
        table = "troncons"
    else:
        data = body if isinstance(body, SousFeederCreate) else SousFeederCreate.model_validate(body)
        record = await repo.create_sous_feeder(db, **data.model_dump())
        resp = SousFeederResponse.model_validate(record)
        table = "sous_feeders"

    await log_audit(
        db,
        table_name=table,
        record_id=record.id,
        action=ACTION_CREATE,
        user_id=user.id,
        new_values={"code": record.code},
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

    values = body.model_dump(exclude_unset=True) if hasattr(body, "model_dump") else body

    if slug == "postes-sources":
        data = body if isinstance(body, PosteSourceUpdate) else PosteSourceUpdate.model_validate(body)
        record = await repo.update_poste_source(db, item_id, **data.model_dump(exclude_unset=True))
        resp = PosteSourceResponse.model_validate(record)
        table = "postes_sources"
    elif slug == "feeders":
        data = body if isinstance(body, FeederUpdate) else FeederUpdate.model_validate(body)
        record = await repo.update_feeder(db, item_id, **data.model_dump(exclude_unset=True))
        resp = FeederResponse.model_validate(record)
        table = "feeders"
    elif slug == "postes":
        data = body if isinstance(body, PosteUpdate) else PosteUpdate.model_validate(body)
        record = await repo.update_poste(db, item_id, **data.model_dump(exclude_unset=True))
        resp = PosteResponse.model_validate(record)
        table = "postes"
    elif slug == "troncons":
        data = body if isinstance(body, TronconUpdate) else TronconUpdate.model_validate(body)
        record = await repo.update_troncon(db, item_id, **data.model_dump(exclude_unset=True))
        resp = TronconResponse.model_validate(record)
        table = "troncons"
    else:
        data = body if isinstance(body, SousFeederUpdate) else SousFeederUpdate.model_validate(body)
        record = await repo.update_sous_feeder(db, item_id, **data.model_dump(exclude_unset=True))
        resp = SousFeederResponse.model_validate(record)
        table = "sous_feeders"

    if record is None:
        raise _not_found()

    await log_audit(
        db,
        table_name=table,
        record_id=item_id,
        action=ACTION_UPDATE,
        user_id=user.id,
        new_values=values if isinstance(values, dict) else {},
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

    if slug == "postes-sources":
        await repo.update_poste_source(db, item_id, is_active=False)
        table = "postes_sources"
    elif slug == "feeders":
        await repo.update_feeder(db, item_id, is_active=False)
        table = "feeders"
    elif slug == "postes":
        await repo.update_poste(db, item_id, is_active=False)
        table = "postes"
    elif slug == "troncons":
        await repo.update_troncon(db, item_id, is_active=False)
        table = "troncons"
    else:
        await repo.update_sous_feeder(db, item_id, is_active=False)
        table = "sous_feeders"

    await log_audit(
        db,
        table_name=table,
        record_id=item_id,
        action=ACTION_DELETE,
        user_id=user.id,
        new_values={"is_active": False},
    )


def _conflict(code: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"status": "error", "data": None, "error": f"Code '{code}' déjà utilisé"},
    )
