"""Repository RBAC — lecture des rôles, permissions et scopes utilisateur."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.utilisateurs import Permission, Role, RolePermission, UserRole


async def get_user_permissions(db: AsyncSession, user_id: int) -> list[str]:
    """Retourne la liste des permissions de l'utilisateur sous la forme "ressource:action".

    Consolide toutes les permissions issues de tous les rôles actifs de l'utilisateur.
    Un utilisateur avec plusieurs rôles reçoit l'union des permissions de chacun.
    """
    result = await db.execute(
        select(UserRole)
        .where(UserRole.utilisateur_id == user_id)
        .options(
            selectinload(UserRole.role)
            .selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
    )
    user_roles = result.scalars().all()

    permissions: set[str] = set()
    for user_role in user_roles:
        for rp in user_role.role.role_permissions:
            permissions.add(f"{rp.permission.ressource}:{rp.permission.action}")

    return sorted(permissions)


async def get_user_roles(db: AsyncSession, user_id: int) -> list[str]:
    """Retourne la liste des noms de rôles de l'utilisateur (ex : ["BCC"])."""
    result = await db.execute(
        select(UserRole)
        .where(UserRole.utilisateur_id == user_id)
        .options(selectinload(UserRole.role))
    )
    user_roles = result.scalars().all()
    return [ur.role.nom for ur in user_roles]


async def get_user_scope(db: AsyncSession, user_id: int) -> int | None:
    """Retourne le scope_service_id du premier rôle de l'utilisateur.

    Retourne None pour les rôles nationaux (ADMIN_SCR, ADMIN_DISPATCHING,
    ADMIN_SAQS, DISPATCHER) qui n'ont pas de restriction de périmètre.
    """
    result = await db.execute(
        select(UserRole.scope_service_id)
        .where(UserRole.utilisateur_id == user_id)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row


async def get_role_by_name(db: AsyncSession, role_name: str) -> Role | None:
    """Retourne un rôle par son nom, ou None s'il n'existe pas."""
    result = await db.execute(
        select(Role)
        .where(Role.nom == role_name)
        .options(
            selectinload(Role.role_permissions)
            .selectinload(RolePermission.permission)
        )
    )
    return result.scalar_one_or_none()


async def get_permission_by_key(
    db: AsyncSession,
    ressource: str,
    action: str,
) -> Permission | None:
    """Retourne une permission par la paire (ressource, action), ou None."""
    result = await db.execute(
        select(Permission).where(
            Permission.ressource == ressource,
            Permission.action == action,
        )
    )
    return result.scalar_one_or_none()
