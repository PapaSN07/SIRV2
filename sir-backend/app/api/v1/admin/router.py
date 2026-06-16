from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.admin import (
    AppSettingsResponse,
    AppSettingsUpdate,
    AuditLogResponse,
    PermissionInfo,
    ResetPasswordRequest,
    RoleDetailResponse,
    UtilisateurCreate,
    UtilisateurResponse,
    UtilisateurUpdate,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services import admin_advanced_service, admin_utilisateur_service

router = APIRouter()

@router.get(
    "/utilisateurs",
    response_model=ApiResponse[PaginatedResponse[UtilisateurResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée des utilisateurs (filtrée par direction admin)",
)
async def list_utilisateurs(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "read")
    ),
) -> ApiResponse[PaginatedResponse[UtilisateurResponse]]:
    result = await admin_utilisateur_service.list_utilisateurs(
        db, current_user, page, page_size
    )
    return ApiResponse.success(result)


@router.post(
    "/utilisateurs",
    response_model=ApiResponse[UtilisateurResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un utilisateur",
)
async def create_utilisateur(
    body: UtilisateurCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "create")
    ),
) -> ApiResponse[UtilisateurResponse]:
    result = await admin_utilisateur_service.create_utilisateur(db, current_user, body)
    return ApiResponse.success(result)


@router.put(
    "/utilisateurs/{user_id}",
    response_model=ApiResponse[UtilisateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Mettre à jour le profil d'un utilisateur",
)
async def update_utilisateur(
    user_id: int,
    body: UtilisateurUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "update")
    ),
) -> ApiResponse[UtilisateurResponse]:
    result = await admin_utilisateur_service.update_utilisateur(
        db, current_user, user_id, body
    )
    return ApiResponse.success(result)


@router.patch(
    "/utilisateurs/{user_id}/activer",
    response_model=ApiResponse[UtilisateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Activer un compte utilisateur",
)
async def activer_utilisateur(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "update")
    ),
) -> ApiResponse[UtilisateurResponse]:
    result = await admin_utilisateur_service.activer_utilisateur(
        db, current_user, user_id
    )
    return ApiResponse.success(result)


@router.patch(
    "/utilisateurs/{user_id}/desactiver",
    response_model=ApiResponse[UtilisateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Désactiver un compte utilisateur",
)
async def desactiver_utilisateur(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "update")
    ),
) -> ApiResponse[UtilisateurResponse]:
    result = await admin_utilisateur_service.desactiver_utilisateur(
        db, current_user, user_id
    )
    return ApiResponse.success(result)


@router.post(
    "/utilisateurs/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Réinitialiser le mot de passe d'un utilisateur",
)
async def reset_password(
    user_id: int,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("admin_utilisateurs", "update")
    ),
) -> None:
    await admin_utilisateur_service.reset_password(db, current_user, user_id, body)


@router.get(
    "/roles",
    response_model=ApiResponse[list[RoleDetailResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("admin_utilisateurs", "read")),
) -> ApiResponse[list[RoleDetailResponse]]:
    result = await admin_advanced_service.list_roles(db)
    return ApiResponse.success(result)


@router.get(
    "/permissions",
    response_model=ApiResponse[list[PermissionInfo]],
    status_code=status.HTTP_200_OK,
)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("admin_utilisateurs", "read")),
) -> ApiResponse[list[PermissionInfo]]:
    result = await admin_advanced_service.list_permissions(db)
    return ApiResponse.success(result)


@router.get(
    "/audit-log",
    response_model=ApiResponse[PaginatedResponse[AuditLogResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    table_name: str | None = Query(None),
    user_id: int | None = Query(None, ge=1),
    date_debut: datetime | None = Query(None),
    date_fin: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("admin_utilisateurs", "read")),
) -> ApiResponse[PaginatedResponse[AuditLogResponse]]:
    result = await admin_advanced_service.list_audit_log(
        db,
        page=page,
        page_size=page_size,
        table_name=table_name,
        user_id=user_id,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.get(
    "/settings",
    response_model=ApiResponse[AppSettingsResponse],
    status_code=status.HTTP_200_OK,
)
async def get_settings(
    current_user: Utilisateur = Depends(require_permission("admin_utilisateurs", "read")),
) -> ApiResponse[AppSettingsResponse]:
    return ApiResponse.success(admin_advanced_service.get_app_settings())


@router.patch(
    "/settings",
    response_model=ApiResponse[AppSettingsResponse],
    status_code=status.HTTP_200_OK,
)
async def update_settings(
    body: AppSettingsUpdate,
    current_user: Utilisateur = Depends(require_permission("admin_utilisateurs", "update")),
) -> ApiResponse[AppSettingsResponse]:
    result = admin_advanced_service.update_app_settings(body)
    return ApiResponse.success(result)
