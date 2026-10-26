"""Seeder RBAC — initialise les 7 rôles et leurs permissions.

Idempotent : peut être exécuté plusieurs fois sans créer de doublons.
Utilise un pattern upsert basé sur les contraintes d'unicité existantes.

Usage depuis le point d'entrée de l'application ou une commande CLI :
    from app.models.seed.seed_rbac import seed_rbac
    await seed_rbac(db)
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from app.core.security import hash_password
from app.models.utilisateurs import Permission, Role, RolePermission, UserRole, Utilisateur

# ---------------------------------------------------------------------------
# Définition des rôles et de leurs permissions
# ---------------------------------------------------------------------------

# Format : (ressource, action, description_optionnelle)
_PERMISSIONS: list[tuple[str, str, str]] = [
    ("interruptions_distribution", "create", "Créer une interruption distribution"),
    ("interruptions_distribution", "read", "Lire les interruptions distribution"),
    ("interruptions_distribution", "update", "Modifier une interruption distribution"),
    ("interruptions_distribution", "validate", "Valider une interruption distribution"),
    ("interruptions_transport", "create", "Créer une interruption transport"),
    ("interruptions_transport", "read", "Lire les interruptions transport"),
    ("interruptions_transport", "update", "Modifier une interruption transport"),
    ("interruptions_transport", "validate", "Valider une interruption transport"),
    ("indicateurs", "read", "Lire les indicateurs END/SAIFI/SAIDI"),
    ("assistant", "read", "Consulter l'Assistant risque panne / travaux"),
    ("assistant", "admin", "Recalculer les scores Assistant ML"),
    ("rapports", "read", "Lire et générer les rapports"),
    ("notifications", "read", "Lire les notifications et traces d'envoi"),
    ("notifications", "admin", "Administrer les destinataires notifications"),
    ("napt", "read", "Lire les NAPT"),
    ("napt", "create", "Créer un NAPT"),
    ("napt", "update", "Modifier un NAPT"),
    ("napt", "validate", "Valider un NAPT"),
    ("reseau", "read", "Lire les données réseau (feeders, postes…)"),
    ("admin_utilisateurs", "create", "Créer un utilisateur"),
    ("admin_utilisateurs", "read", "Lire les utilisateurs"),
    ("admin_utilisateurs", "update", "Modifier un utilisateur"),
]

# Format : (nom_role, description, [(ressource, action), ...])
_ROLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "BCC",
        "Bureau Central de Conduite — saisie interruptions Dakar (SDDV, SDPG, SDRBD · périmètre régional Dakar)",
        [
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("indicateurs", "read"),
            ("assistant", "read"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("notifications", "admin"),
            ("napt", "read"),
            ("napt", "create"),
            ("napt", "update"),
        ],
    ),
    (
        "BRC",
        "Bureau Régional de Conduite — saisie interruptions région (SDRCO*, SDRCE*, SDRN*, SDRS · périmètre : sa région)",
        [
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("indicateurs", "read"),
            ("assistant", "read"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("notifications", "admin"),
        ],
    ),
    (
        "DISPATCHER",
        "Opérateur réseau transport HTB — périmètre national transport",
        [
            ("interruptions_transport", "create"),
            ("interruptions_transport", "read"),
            ("interruptions_transport", "update"),
            ("rapports", "read"),
            ("notifications", "read"),
        ],
    ),
    (
        "ADMIN_SCR",
        "Administrateur distribution national — ne peut pas accéder aux données transport",
        [
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
            ("interruptions_distribution", "validate"),
            ("admin_utilisateurs", "create"),
            ("admin_utilisateurs", "read"),
            ("admin_utilisateurs", "update"),
            ("indicateurs", "read"),
            ("assistant", "read"),
            ("assistant", "admin"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("notifications", "admin"),
            ("napt", "read"),
            ("napt", "create"),
            ("napt", "update"),
            ("napt", "validate"),
        ],
    ),
    (
        "ADMIN_DISPATCHING",
        "Administrateur transport national — ne peut pas accéder aux données distribution",
        [
            ("interruptions_transport", "create"),
            ("interruptions_transport", "read"),
            ("interruptions_transport", "update"),
            ("interruptions_transport", "validate"),
            ("admin_utilisateurs", "create"),
            ("admin_utilisateurs", "read"),
            ("admin_utilisateurs", "update"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("notifications", "admin"),
        ],
    ),
    (
        "ADMIN_SAQS",
        "Administrateur SAQS — lecture seule sur tout, jamais de création/modification",
        [
            ("interruptions_distribution", "read"),
            ("interruptions_transport", "read"),
            ("interruptions_distribution", "validate"),
            ("indicateurs", "read"),
            ("assistant", "read"),
            ("assistant", "admin"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("napt", "read"),
            ("napt", "validate"),
            ("reseau", "read"),
        ],
    ),
    (
        "SUPERVISEUR",
        "Superviseur — validation des interruptions sur son service",
        [
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "validate"),
            ("interruptions_transport", "read"),
            ("indicateurs", "read"),
            ("assistant", "read"),
            ("rapports", "read"),
            ("notifications", "read"),
            ("napt", "read"),
            ("napt", "validate"),
        ],
    ),
]

_SUPERADMIN_ROLE = "SUPERADMIN"
_SUPERADMIN_LOGIN = "superadmin.dev"


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------


async def _fetch_one_or_none(result) -> object | None:
    """Consomme le curseur ODBC (évite « connexion occupée » sur SQL Server)."""
    try:
        return result.scalar_one_or_none()
    finally:
        close = getattr(result, "close", None)
        if close is not None:
            closed = close()
            if asyncio.iscoroutine(closed):
                await closed


async def _upsert_permission(
    db: AsyncSession,
    ressource: str,
    action: str,
    description: str,
) -> Permission:
    """Récupère la permission existante ou la crée — jamais de doublon."""
    result = await db.execute(
        select(Permission).where(
            Permission.ressource == ressource,
            Permission.action == action,
        )
    )
    permission = await _fetch_one_or_none(result)
    if permission is None:
        permission = Permission(
            ressource=ressource,
            action=action,
            description=description,
        )
        db.add(permission)
        await db.flush()  # obtenir l'id sans commit
    return permission


async def _upsert_role(
    db: AsyncSession,
    nom: str,
    description: str,
) -> Role:
    """Récupère le rôle existant ou le crée — jamais de doublon."""
    result = await db.execute(
        select(Role).options(noload(Role.role_permissions)).where(Role.nom == nom)
    )
    role = await _fetch_one_or_none(result)
    if role is None:
        role = Role(nom=nom, description=description, is_active=True)
        db.add(role)
        await db.flush()
    return role


async def _load_role_permission_links(db: AsyncSession) -> set[tuple[int, int]]:
    """Charge toutes les associations existantes (une seule requête ODBC)."""
    result = await db.execute(select(RolePermission.role_id, RolePermission.permission_id))
    try:
        return {(int(row[0]), int(row[1])) for row in result.all()}
    finally:
        close = getattr(result, "close", None)
        if close is not None:
            closed = close()
            if asyncio.iscoroutine(closed):
                await closed


def _ensure_role_permission(
    links: set[tuple[int, int]],
    db: AsyncSession,
    role_id: int,
    permission_id: int,
) -> None:
    """Crée l'association role-permission si elle n'existe pas déjà (cache mémoire)."""
    key = (role_id, permission_id)
    if key in links:
        return
    db.add(RolePermission(role_id=role_id, permission_id=permission_id))
    links.add(key)


async def _upsert_role_permission(
    db: AsyncSession,
    links: set[tuple[int, int]],
    role_id: int,
    permission_id: int,
) -> None:
    """Crée l'association role-permission si elle n'existe pas déjà."""
    _ensure_role_permission(links, db, role_id, permission_id)


async def _seed_superadmin_role_and_user(
    db: AsyncSession,
    permission_map: dict[tuple[str, str], Permission],
    links: set[tuple[int, int]],
    password: str,
) -> None:
    """Rôle et compte dev SUPERADMIN — toutes les permissions, accès total."""
    role = await _upsert_role(
        db,
        _SUPERADMIN_ROLE,
        "Dev uniquement — accès total à toutes les fonctionnalités",
    )
    for perm in permission_map.values():
        await _upsert_role_permission(db, links, role.id, perm.id)

    result = await db.execute(select(Utilisateur).where(Utilisateur.login == _SUPERADMIN_LOGIN))
    user = await _fetch_one_or_none(result)
    if user is not None:
        return

    user = Utilisateur(
        login=_SUPERADMIN_LOGIN,
        password_hash=hash_password(password),
        nom="Super",
        prenom="Admin",
        email=f"{_SUPERADMIN_LOGIN}@senelec.sn",
        telephone=None,
        is_active=True,
        premiere_connexion=False,
    )
    db.add(user)
    await db.flush()

    db.add(
        UserRole(
            utilisateur_id=user.id,
            role_id=role.id,
            scope_service_id=None,
        )
    )
    await db.flush()


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------


async def seed_rbac(
    db: AsyncSession,
    *,
    with_superadmin: bool = False,
    superadmin_password: str | None = None,
) -> None:
    """Initialise les rôles et permissions RBAC du système SIR.

    Le compte ``superadmin.dev`` (accès total) n'est créé que sur demande
    explicite (``with_superadmin=True``, seed de développement) : jamais
    par le seed RBAC exécuté sur une base partagée ou de production.

    Idempotent : safe à appeler plusieurs fois en développement et au démarrage
    en environnement de staging. En production, appeler une seule fois via
    une migration Alembic ou une commande CLI dédiée.

    Args:
        db: Session SQLAlchemy async avec transaction ouverte.
    """
    # Étape 1 — Créer ou récupérer toutes les permissions
    permission_map: dict[tuple[str, str], Permission] = {}
    for ressource, action, description in _PERMISSIONS:
        perm = await _upsert_permission(db, ressource, action, description)
        permission_map[(ressource, action)] = perm

    # Étape 2 — Créer ou récupérer les rôles et leurs associations de permissions
    links = await _load_role_permission_links(db)
    for nom_role, description_role, role_perms in _ROLES:
        role = await _upsert_role(db, nom_role, description_role)

        for ressource, action in role_perms:
            permission = permission_map[(ressource, action)]
            await _upsert_role_permission(db, links, role.id, permission.id)

    if with_superadmin:
        if not superadmin_password:
            raise ValueError("superadmin_password requis pour créer le compte superadmin.dev")
        await _seed_superadmin_role_and_user(db, permission_map, links, superadmin_password)

    # Flush final pour persister toutes les associations avant commit externe
    await db.flush()
