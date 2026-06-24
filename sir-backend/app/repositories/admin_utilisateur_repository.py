"""Repository CRUD admin — gestion des utilisateurs avec filtre direction."""

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.utilisateurs import Role, UserRole, Utilisateur

# Rôles gérés par chaque direction admin
DISTRIBUTION_ROLE_NAMES: frozenset[str] = frozenset(
    {"BCC", "BRC", "ADMIN_SCR", "SUPERVISEUR"}
)
TRANSPORT_ROLE_NAMES: frozenset[str] = frozenset({"DISPATCHER", "ADMIN_DISPATCHING"})

_DIRECTION_ROLES: dict[str, frozenset[str]] = {
    "distribution": DISTRIBUTION_ROLE_NAMES,
    "transport": TRANSPORT_ROLE_NAMES,
}


def _utilisateur_options() -> list:
    return [
        selectinload(Utilisateur.user_roles)
        .selectinload(UserRole.role)
    ]


def allowed_roles_for_direction(direction: str) -> frozenset[str]:
    return _DIRECTION_ROLES[direction]


def user_has_direction_role(user: Utilisateur, direction: str) -> bool:
    """Vérifie si l'utilisateur possède au moins un rôle de la direction."""
    allowed = allowed_roles_for_direction(direction)
    return any(ur.role.nom in allowed for ur in user.user_roles)


async def get_by_id(db: AsyncSession, user_id: int) -> Utilisateur | None:
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == user_id)
        .options(*_utilisateur_options())
    )
    return result.scalar_one_or_none()


async def get_by_login(db: AsyncSession, login: str) -> Utilisateur | None:
    result = await db.execute(
        select(Utilisateur).where(Utilisateur.login == login)
    )
    return result.scalar_one_or_none()


async def get_role_by_id(db: AsyncSession, role_id: int) -> Role | None:
    result = await db.execute(select(Role).where(Role.id == role_id))
    return result.scalar_one_or_none()


async def list_by_direction(
    db: AsyncSession,
    direction: str,
    page: int,
    page_size: int,
) -> tuple[list[Utilisateur], int]:
    """Liste paginée des utilisateurs ayant au moins un rôle de la direction."""
    allowed = allowed_roles_for_direction(direction)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    user_ids_subq = (
        select(UserRole.utilisateur_id)
        .join(Role, UserRole.role_id == Role.id)
        .where(Role.nom.in_(allowed))
        .distinct()
    )

    count_result = await db.execute(
        select(func.count()).select_from(user_ids_subq.subquery())
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id.in_(user_ids_subq))
        .options(*_utilisateur_options())
        .order_by(Utilisateur.id)
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def list_all(
    db: AsyncSession,
    page: int,
    page_size: int,
) -> tuple[list[Utilisateur], int]:
    """Liste paginée de tous les utilisateurs (super admin dev)."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    count_result = await db.execute(select(func.count()).select_from(Utilisateur))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Utilisateur)
        .options(*_utilisateur_options())
        .order_by(Utilisateur.id)
        .offset(offset)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def create(
    db: AsyncSession,
    *,
    login: str,
    password_hash: str,
    nom: str,
    prenom: str,
    email: str | None,
    telephone: str | None,
    roles: list[tuple[int, int | None]],
) -> Utilisateur:
    user = Utilisateur(
        login=login,
        password_hash=password_hash,
        nom=nom,
        prenom=prenom,
        email=email,
        telephone=telephone,
        is_active=True,
        premiere_connexion=True,
    )
    db.add(user)
    await db.flush()

    for role_id, scope_service_id in roles:
        db.add(
            UserRole(
                utilisateur_id=user.id,
                role_id=role_id,
                scope_service_id=scope_service_id,
            )
        )
    await db.flush()

    created = await get_by_id(db, user.id)
    assert created is not None
    return created


async def update_profile(
    db: AsyncSession,
    user: Utilisateur,
    *,
    nom: str | None,
    prenom: str | None,
    email: str | None,
    telephone: str | None,
) -> Utilisateur:
    values: dict = {}
    if nom is not None:
        values["nom"] = nom
    if prenom is not None:
        values["prenom"] = prenom
    if email is not None:
        values["email"] = email
    if telephone is not None:
        values["telephone"] = telephone

    if values:
        await db.execute(
            update(Utilisateur).where(Utilisateur.id == user.id).values(**values)
        )
        await db.flush()

    updated = await get_by_id(db, user.id)
    assert updated is not None
    return updated


async def replace_roles(
    db: AsyncSession,
    user_id: int,
    roles: list[tuple[int, int | None]],
) -> None:
    await db.execute(delete(UserRole).where(UserRole.utilisateur_id == user_id))
    await db.flush()

    for role_id, scope_service_id in roles:
        db.add(
            UserRole(
                utilisateur_id=user_id,
                role_id=role_id,
                scope_service_id=scope_service_id,
            )
        )
    await db.flush()


async def set_active(db: AsyncSession, user_id: int, is_active: bool) -> Utilisateur | None:
    await db.execute(
        update(Utilisateur).where(Utilisateur.id == user_id).values(is_active=is_active)
    )
    await db.flush()
    return await get_by_id(db, user_id)


async def reset_password(
    db: AsyncSession,
    user_id: int,
    password_hash: str,
) -> Utilisateur | None:
    await db.execute(
        update(Utilisateur)
        .where(Utilisateur.id == user_id)
        .values(password_hash=password_hash, premiere_connexion=False)
    )
    await db.flush()
    return await get_by_id(db, user_id)
