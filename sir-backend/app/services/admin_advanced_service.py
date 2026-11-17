"""Services administration avancée — rôles, audit, paramètres."""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rbac_helpers import ROLES_SYSTEME, SUPERADMIN_ROLE, is_superadmin, role_names
from app.models.utilisateurs import Permission, Role, Utilisateur
from app.repositories import audit_repository, role_repository
from app.schemas.admin import (
    AppSettingsResponse,
    AppSettingsUpdate,
    AuditLogResponse,
    PermissionInfo,
    RoleCreate,
    RoleDetailResponse,
    RoleUpdate,
)
from app.utils.audit import ACTION_CREATE, ACTION_UPDATE, log_audit
from app.schemas.common import PaginatedResponse


# Seul un SUPERADMIN attribue la gestion des rôles (sinon un admin pourrait s'octroyer n'importe quel droit)
_RESSOURCES_RESERVEES: frozenset[str] = frozenset({"admin_roles"})


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _role_response(role: Role, nombre_utilisateurs: int = 0) -> RoleDetailResponse:
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
    return RoleDetailResponse(
        id=role.id,
        nom=role.nom,
        description=role.description,
        permissions=sorted(perms, key=lambda p: (p.ressource, p.action)),
        is_active=role.is_active,
        systeme=role.nom in ROLES_SYSTEME,
        nombre_utilisateurs=nombre_utilisateurs,
    )


async def list_roles(db: AsyncSession) -> list[RoleDetailResponse]:
    """Rôles (actifs puis désactivés) avec leurs droits et leur nombre d'utilisateurs."""
    roles = await role_repository.lister_roles(db)
    comptes = await role_repository.nombre_utilisateurs_par_role(db)
    items = [_role_response(role, comptes.get(role.id, 0)) for role in roles]
    return sorted(items, key=lambda r: (not r.is_active, r.nom))


async def _verifier_permissions(
    db: AsyncSession, current_user: Utilisateur, permission_ids: list[int]
) -> list[int]:
    ids = sorted(set(permission_ids))
    perms = await role_repository.permissions_par_ids(db, ids)
    if len(perms) != len(ids):
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Droit inconnu dans la sélection")
    if not is_superadmin(current_user) and any(p.ressource in _RESSOURCES_RESERVEES for p in perms):
        raise _erreur(status.HTTP_403_FORBIDDEN, "Seul un super-administrateur attribue la gestion des rôles")
    return ids


async def create_role(db: AsyncSession, current_user: Utilisateur, body: RoleCreate) -> RoleDetailResponse:
    nom = body.nom.strip().upper()
    if await role_repository.role_par_nom(db, nom) is not None:
        raise _erreur(status.HTTP_409_CONFLICT, f"Le rôle {nom} existe déjà")
    ids = await _verifier_permissions(db, current_user, body.permission_ids)
    role = await role_repository.creer_role(db, nom, (body.description or "").strip() or None)
    await role_repository.remplacer_permissions(db, role.id, ids)
    await log_audit(
        db,
        table_name="roles",
        record_id=role.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={"nom": nom, "permission_ids": ids},
    )
    db.expire(role)
    cree = await role_repository.get_role(db, role.id)
    return _role_response(cree)  # type: ignore[arg-type]


async def update_role(
    db: AsyncSession, current_user: Utilisateur, role_id: int, body: RoleUpdate
) -> RoleDetailResponse:
    role = await role_repository.get_role(db, role_id)
    if role is None:
        raise _erreur(status.HTTP_404_NOT_FOUND, "Rôle introuvable")
    if role.nom == SUPERADMIN_ROLE:
        raise _erreur(status.HTTP_403_FORBIDDEN, "Le rôle SUPERADMIN ne se modifie pas")
    if not is_superadmin(current_user) and role.nom in role_names(current_user):
        raise _erreur(
            status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas modifier les droits d'un rôle que vous détenez"
        )
    anciens = sorted(rp.permission_id for rp in role.role_permissions)
    if body.description is not None:
        role.description = body.description.strip() or None
    if body.is_active is not None and body.is_active != role.is_active:
        if role.nom in ROLES_SYSTEME:
            raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Un rôle prévu par SIRV2 ne peut pas être désactivé")
        role.is_active = body.is_active
    nouveaux = anciens
    if body.permission_ids is not None:
        demandes = set(body.permission_ids)
        # Un droit réservé déjà présent peut être conservé ; seul l'ajout est contrôlé
        ajoutes = sorted(demandes - set(anciens))
        await _verifier_permissions(db, current_user, ajoutes)
        if len(await role_repository.permissions_par_ids(db, sorted(demandes))) != len(demandes):
            raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, "Droit inconnu dans la sélection")
        nouveaux = sorted(demandes)
        await role_repository.remplacer_permissions(db, role.id, nouveaux)
    await db.flush()
    await log_audit(
        db,
        table_name="roles",
        record_id=role.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values={"permission_ids": anciens},
        new_values={"permission_ids": nouveaux, "is_active": role.is_active, "description": role.description},
    )
    db.expire(role)
    modifie = await role_repository.get_role(db, role.id)
    comptes = await role_repository.nombre_utilisateurs_par_role(db)
    return _role_response(modifie, comptes.get(role.id, 0))  # type: ignore[arg-type]


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
