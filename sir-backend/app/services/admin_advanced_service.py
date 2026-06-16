"""Services administration avancée — rôles, audit, paramètres."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.utilisateurs import Permission, Role, RolePermission
from app.repositories import audit_repository
from app.schemas.admin import (
    AppSettingsResponse,
    AppSettingsUpdate,
    AuditLogResponse,
    PermissionInfo,
    RoleDetailResponse,
)
from app.schemas.common import PaginatedResponse


async def list_roles(db: AsyncSession) -> list[RoleDetailResponse]:
    result = await db.execute(
        select(Role)
        .where(Role.is_active.is_(True))
        .options(
            selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
        .order_by(Role.nom)
    )
    roles = result.scalars().unique().all()
    items: list[RoleDetailResponse] = []
    for role in roles:
        perms = [
            PermissionInfo(
                id=rp.permission.id,
                ressource=rp.permission.ressource,
                action=rp.permission.action,
                description=rp.permission.description,
            )
            for rp in role.role_permissions
            if rp.permission is not None
        ]
        items.append(
            RoleDetailResponse(
                id=role.id,
                nom=role.nom,
                description=role.description,
                permissions=perms,
            )
        )
    return items


async def list_permissions(db: AsyncSession) -> list[PermissionInfo]:
    result = await db.execute(select(Permission).order_by(Permission.ressource, Permission.action))
    return [
        PermissionInfo(
            id=p.id,
            ressource=p.ressource,
            action=p.action,
            description=p.description,
        )
        for p in result.scalars().all()
    ]


async def list_audit_log(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    table_name: str | None = None,
    user_id: int | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
) -> PaginatedResponse[AuditLogResponse]:
    result = await audit_repository.list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        table_name=table_name,
        user_id=user_id,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    items = [
        AuditLogResponse(
            id=log.id,
            table_name=log.table_name,
            record_id=log.record_id,
            action=log.action,
            user_id=log.user_id,
            user_login=log.user.login if log.user else None,
            old_values=log.old_values,
            new_values=log.new_values,
            created_at=log.created_at,
        )
        for log in result.items
    ]
    return PaginatedResponse(
        items=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
    )


def get_app_settings() -> AppSettingsResponse:
    return AppSettingsResponse(
        sms_gateway_url=settings.sms_gateway_url or None,
        smtp_host=settings.smtp_host or None,
        smtp_port=settings.smtp_port,
        smtp_user=settings.smtp_user or None,
        seuil_fugitif_minutes=getattr(settings, "seuil_fugitif_minutes", 5),
        environment=settings.environment,
    )


def update_app_settings(body: AppSettingsUpdate) -> AppSettingsResponse:
    if body.seuil_fugitif_minutes is not None:
        settings.seuil_fugitif_minutes = body.seuil_fugitif_minutes
    return get_app_settings()
