"""Service métier — gestion destinataires notifications (Sprint 8.3)."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import check_service_scope
from app.core.rbac_helpers import is_superadmin
from app.models.notifications import Destinataire
from app.models.utilisateurs import Utilisateur
from app.repositories import destinataire_repository as repo
from app.repositories.geo_scope_repository import service_in_region
from app.schemas.common import PaginatedResponse
from app.schemas.notifications import (
    DestinataireCreate,
    DestinataireResponse,
    DestinataireUpdate,
    GroupeEnvoiResponse,
)
from app.utils.pagination import paginate

_NATIONAL_ROLES = frozenset({"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS"})
_REGION_ROLES = frozenset({"BCC", "BRC"})
_SERVICE_ROLES = frozenset({"SUPERVISEUR"})
_ADMIN_ROLES = frozenset({"ADMIN_SCR", "ADMIN_DISPATCHING", "BCC", "BRC"})


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def _ensure_can_admin(user: Utilisateur) -> None:
    if is_superadmin(user):
        return
    if not _user_role_names(user).intersection(_ADMIN_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Rôle non autorisé pour administrer les destinataires",
            },
        )


def _to_response(record: Destinataire) -> DestinataireResponse:
    reponse = DestinataireResponse.model_validate(record)
    reponse.groupe_libelle = record.groupe.libelle if record.groupe_id and record.groupe else None
    return reponse


async def _resolve_list_scope(
    db: AsyncSession,
    user: Utilisateur,
    service_id: int | None,
) -> tuple[int | None, list[int] | None, int | None, int | None]:
    roles = _user_role_names(user)

    if is_superadmin(user) or roles.intersection(_NATIONAL_ROLES):
        return service_id, None, None, None

    if roles.intersection(_REGION_ROLES):
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
        if service_id is not None and not await service_in_region(db, service_id, region_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "data": None, "error": "Hors périmètre régional"},
            )
        return service_id, None, region_id, None

    if roles.intersection(_SERVICE_ROLES):
        user_service_id = user.user_roles[0].scope_service_id
        if user_service_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre de service non configuré pour ce compte",
                },
            )
        if service_id is not None and service_id != user_service_id:
            check_service_scope(user, service_id)
        return None, None, None, user_service_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Rôle non autorisé pour consulter les destinataires",
        },
    )


async def assert_destinataire_in_scope(
    db: AsyncSession,
    user: Utilisateur,
    record: Destinataire,
) -> None:
    if is_superadmin(user):
        return
    if record.service_id is None:
        if _user_role_names(user).intersection(_NATIONAL_ROLES):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Hors périmètre",
            },
        )

    roles = _user_role_names(user)
    if roles.intersection(_NATIONAL_ROLES):
        return

    if roles.intersection(_SERVICE_ROLES):
        check_service_scope(user, record.service_id)
        return

    if roles.intersection(_REGION_ROLES):
        region_id = user.user_roles[0].scope_service_id
        if region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "data": None, "error": "Périmètre non configuré"},
            )
        if not await service_in_region(db, record.service_id, region_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"status": "error", "data": None, "error": "Hors périmètre régional"},
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"status": "error", "data": None, "error": "Hors périmètre"},
    )


def _resolve_write_service_id(user: Utilisateur, service_id: int | None) -> int | None:
    roles = _user_role_names(user)
    if is_superadmin(user) or roles.intersection(_NATIONAL_ROLES):
        return service_id
    if roles.intersection(_SERVICE_ROLES):
        user_service_id = user.user_roles[0].scope_service_id
        if service_id is not None and service_id != user_service_id:
            check_service_scope(user, service_id)
        return user_service_id
    if roles.intersection(_REGION_ROLES):
        return service_id
    return service_id


async def list_destinataires(
    db: AsyncSession,
    user: Utilisateur,
    *,
    page: int,
    page_size: int,
    service_id: int | None,
    is_active: bool | None,
) -> PaginatedResponse[DestinataireResponse]:
    filter_service_id, service_ids_scope, region_id_scope, force_service_id = (
        await _resolve_list_scope(db, user, service_id)
    )
    query = repo.build_list_query(
        service_id=filter_service_id,
        is_active=is_active,
        service_ids_scope=service_ids_scope,
        region_id_scope=region_id_scope,
        force_service_id=force_service_id,
    )
    result = await paginate(db, query, page, page_size, scalar_type=Destinataire)
    return PaginatedResponse(
        items=[_to_response(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


async def get_destinataire(
    db: AsyncSession,
    user: Utilisateur,
    destinataire_id: int,
) -> DestinataireResponse:
    record = await repo.get_by_id(db, destinataire_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Destinataire introuvable"},
        )
    await assert_destinataire_in_scope(db, user, record)
    return _to_response(record)


async def create_destinataire(
    db: AsyncSession,
    user: Utilisateur,
    body: DestinataireCreate,
) -> DestinataireResponse:
    _ensure_can_admin(user)
    resolved_service_id = _resolve_write_service_id(user, body.service_id)
    if resolved_service_id is not None:
        check_service_scope(user, resolved_service_id)

    record = await repo.create(
        db,
        nom=body.nom,
        telephone=body.telephone,
        email=body.email,
        utilisateur_id=body.utilisateur_id,
        service_id=resolved_service_id,
        fonction=body.fonction,
        groupe_id=body.groupe_id,
    )
    await db.commit()
    await db.refresh(record)
    return _to_response(record)


async def update_destinataire(
    db: AsyncSession,
    user: Utilisateur,
    destinataire_id: int,
    body: DestinataireUpdate,
) -> DestinataireResponse:
    _ensure_can_admin(user)
    record = await repo.get_by_id(db, destinataire_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Destinataire introuvable"},
        )
    await assert_destinataire_in_scope(db, user, record)

    updates = body.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"])

    merged_phone = updates.get("telephone", record.telephone)
    merged_email = updates.get("email", record.email)
    if not merged_phone and not merged_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "error",
                "data": None,
                "error": "Au moins un téléphone ou un email est requis",
            },
        )

    if "service_id" in updates and updates["service_id"] is not None:
        check_service_scope(user, updates["service_id"])

    record = await repo.update(db, record, **updates)
    await db.commit()
    await db.refresh(record)
    return _to_response(record)


async def delete_destinataire(
    db: AsyncSession,
    user: Utilisateur,
    destinataire_id: int,
) -> None:
    _ensure_can_admin(user)
    record = await repo.get_by_id(db, destinataire_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "error", "data": None, "error": "Destinataire introuvable"},
        )
    await assert_destinataire_in_scope(db, user, record)
    record.is_active = False
    await db.commit()


async def list_groupes_envoi(db: AsyncSession, user: Utilisateur) -> list[GroupeEnvoiResponse]:
    """Groupes d'envoi SMS avec le nombre de destinataires joignables dans le périmètre de l'utilisateur."""
    filter_service_id, service_ids_scope, region_id_scope, force_service_id = await _resolve_list_scope(db, user, None)
    query = repo.build_list_query(
        service_id=filter_service_id,
        is_active=True,
        service_ids_scope=service_ids_scope,
        region_id_scope=region_id_scope,
        force_service_id=force_service_id,
    )
    lignes = await repo.list_groupes_envoi(db, query)
    return [GroupeEnvoiResponse(id=i, libelle=lib, nb_destinataires=n) for i, lib, n in lignes]
