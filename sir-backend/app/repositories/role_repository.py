"""Accès aux rôles et à la matrice rôles × permissions."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.utilisateurs import Permission, Role, RolePermission, UserRole


async def lister_roles(db: AsyncSession) -> list[Role]:
    """Tous les rôles (actifs et désactivés) avec leurs permissions."""
    result = await db.execute(
        select(Role)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
        .order_by(Role.nom)
    )
    return list(result.scalars().unique().all())


async def get_role(db: AsyncSession, role_id: int) -> Role | None:
    result = await db.execute(
        select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.role_permissions).selectinload(RolePermission.permission))
    )
    return result.scalar_one_or_none()


async def utilisateur_detient_role(db: AsyncSession, utilisateur_id: int, role_id: int) -> bool:
    """Vrai si le compte détient le rôle en base, actif ou non (le compte connecté n'a que ses rôles actifs)."""
    result = await db.execute(
        select(UserRole.id).where(UserRole.utilisateur_id == utilisateur_id, UserRole.role_id == role_id).limit(1)
    )
    return result.first() is not None


async def role_par_nom(db: AsyncSession, nom: str) -> Role | None:
    result = await db.execute(select(Role.id, Role.nom).where(func.upper(Role.nom) == nom.upper()))
    return result.first()  # type: ignore[return-value]


async def permissions_par_ids(db: AsyncSession, ids: list[int]) -> list[Permission]:
    if not ids:
        return []
    result = await db.execute(select(Permission).where(Permission.id.in_(ids)))
    return list(result.scalars().all())


async def nombre_utilisateurs_par_role(db: AsyncSession) -> dict[int, int]:
    result = await db.execute(
        select(UserRole.role_id, func.count(func.distinct(UserRole.utilisateur_id))).group_by(UserRole.role_id)
    )
    return {role_id: int(n) for role_id, n in result.all()}


async def creer_role(db: AsyncSession, nom: str, description: str | None) -> Role:
    role = Role(nom=nom, description=description, is_active=True)
    db.add(role)
    await db.flush()
    return role


async def remplacer_permissions(db: AsyncSession, role_id: int, permission_ids: list[int]) -> None:
    await db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    for permission_id in sorted(set(permission_ids)):
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    await db.flush()
