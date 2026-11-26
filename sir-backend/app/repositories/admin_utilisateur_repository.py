"""Repository CRUD admin — gestion des utilisateurs avec filtre direction."""

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac_helpers import ROLES_SYSTEME
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
    """Vrai si le compte relève entièrement de la direction de l'admin.

    Il faut au moins un rôle, et TOUS les rôles système (ROLES_SYSTEME) du compte dans la direction :
    un compte qui détient aussi SUPERADMIN, ADMIN_SAQS ou un rôle de l'autre direction est hors
    périmètre (sinon un admin de direction pourrait réinitialiser son mot de passe ou lui retirer
    ses autres rôles). Les rôles créés dans la matrice (hors rôles SIRV2) ne gênent pas.
    """
    allowed = allowed_roles_for_direction(direction)
    noms = [ur.role.nom for ur in user.user_roles]
    return bool(noms) and all(nom in allowed for nom in noms if nom in ROLES_SYSTEME)


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


def filtre_recherche(recherche: str | None):
    """Condition « contient » sur login, matricule, nom, prénom, e-mail et « prénom nom » / « nom prénom ».

    Plusieurs mots : chacun doit être trouvé (« diop awa » trouve Awa Diop). Insensible à la casse.
    """
    mots = [m for m in (recherche or "").strip().lower().split() if m][:5]
    if not mots:
        return None
    champs = [
        Utilisateur.login, Utilisateur.matricule, Utilisateur.nom, Utilisateur.prenom, Utilisateur.email,
    ]
    conditions = []
    for mot in mots:
        motif = "%" + mot.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conditions.append(or_(*(func.lower(c).like(motif, escape="\\") for c in champs)))
    return and_(*conditions)


async def list_by_direction(
    db: AsyncSession,
    direction: str,
    page: int,
    page_size: int,
    recherche: str | None = None,
) -> tuple[list[Utilisateur], int]:
    """Liste paginée des comptes de la direction (même règle que `user_has_direction_role`)."""
    allowed = allowed_roles_for_direction(direction)
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    user_ids_subq = (
        select(UserRole.utilisateur_id)
        .join(Role, UserRole.role_id == Role.id)
        .where(or_(Role.nom.in_(allowed), Role.nom.notin_(ROLES_SYSTEME)))
        .distinct()
    )
    # Exclut les comptes qui détiennent un rôle système hors de la direction
    hors_direction_subq = (
        select(UserRole.utilisateur_id)
        .join(Role, UserRole.role_id == Role.id)
        .where(Role.nom.in_(ROLES_SYSTEME - allowed))
        .distinct()
    )

    filtre = filtre_recherche(recherche)
    conditions = [
        Utilisateur.id.in_(user_ids_subq),
        Utilisateur.id.notin_(hors_direction_subq),
    ] + ([filtre] if filtre is not None else [])
    count_result = await db.execute(select(func.count(Utilisateur.id)).where(*conditions))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Utilisateur)
        .where(*conditions)
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
    recherche: str | None = None,
) -> tuple[list[Utilisateur], int]:
    """Liste paginée de tous les utilisateurs (super admin dev)."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    filtre = filtre_recherche(recherche)
    conditions = [filtre] if filtre is not None else []
    count_result = await db.execute(select(func.count(Utilisateur.id)).where(*conditions))
    total = count_result.scalar_one()

    result = await db.execute(
        select(Utilisateur)
        .where(*conditions)
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
    matricule: str | None = None,
    premiere_connexion: bool = True,
) -> Utilisateur:
    user = Utilisateur(
        login=login,
        password_hash=password_hash,
        nom=nom,
        prenom=prenom,
        email=email,
        matricule=matricule,
        telephone=telephone,
        is_active=True,
        premiere_connexion=premiere_connexion,
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
    matricule: str | None = None,
) -> Utilisateur:
    values: dict = {}
    if matricule is not None:
        values["matricule"] = matricule.strip() or None
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


async def logins_existants(db: AsyncSession, logins: list[str]) -> set[str]:
    """Logins (en minuscules) déjà présents dans SIRV2 parmi ceux donnés."""
    if not logins:
        return set()
    minuscules = sorted({login.lower() for login in logins})
    result = await db.execute(select(Utilisateur.login).where(func.lower(Utilisateur.login).in_(minuscules)))
    return {login.lower() for (login,) in result.all()}
