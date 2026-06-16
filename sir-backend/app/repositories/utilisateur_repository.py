from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.utilisateurs import Utilisateur, UserRole, Role, RolePermission


def _utilisateur_options() -> list:
    """Options de chargement eager pour Utilisateur.

    Charge la chaîne complète :
      user_roles → role → role_permissions → permission
    Évite tout lazy load synchrone dans les services et dépendances.
    """
    return [
        selectinload(Utilisateur.user_roles)
        .selectinload(UserRole.role)
        .selectinload(Role.role_permissions)
        .selectinload(RolePermission.permission)
    ]


async def get_by_login(db: AsyncSession, login: str) -> Utilisateur | None:
    """Récupère un utilisateur par son login avec rôles et permissions chargés eagerly."""
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.login == login)
        .options(*_utilisateur_options())
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: int) -> Utilisateur | None:
    """Récupère un utilisateur par son id avec rôles et permissions chargés eagerly."""
    result = await db.execute(
        select(Utilisateur)
        .where(Utilisateur.id == user_id)
        .options(*_utilisateur_options())
    )
    return result.scalar_one_or_none()


async def update_premiere_connexion(db: AsyncSession, user_id: int) -> None:
    """Marque l'utilisateur comme ayant terminé sa première connexion."""
    await db.execute(
        update(Utilisateur)
        .where(Utilisateur.id == user_id)
        .values(premiere_connexion=False)
    )
    await db.flush()


async def update_password(db: AsyncSession, user_id: int, password_hash: str) -> None:
    """Met à jour le hash mot de passe et désactive le flag première connexion."""
    await db.execute(
        update(Utilisateur)
        .where(Utilisateur.id == user_id)
        .values(password_hash=password_hash, premiere_connexion=False)
    )
    await db.flush()
