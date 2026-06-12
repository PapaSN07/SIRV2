"""Seeder RBAC — initialise les 7 rôles et leurs permissions.

Idempotent : peut être exécuté plusieurs fois sans créer de doublons.
Utilise un pattern upsert basé sur les contraintes d'unicité existantes.

Usage depuis le point d'entrée de l'application ou une commande CLI :
    from app.models.seed.seed_rbac import seed_rbac
    await seed_rbac(db)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.utilisateurs import Permission, Role, RolePermission

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
    ("rapports", "read", "Lire et générer les rapports"),
    ("napt", "read", "Lire les NAPT"),
    ("reseau", "read", "Lire les données réseau (feeders, postes…)"),
    ("admin_utilisateurs", "create", "Créer un utilisateur"),
    ("admin_utilisateurs", "read", "Lire les utilisateurs"),
    ("admin_utilisateurs", "update", "Modifier un utilisateur"),
]

# Format : (nom_role, description, [(ressource, action), ...])
_ROLES: list[tuple[str, str, list[tuple[str, str]]]] = [
    (
        "BCC",
        "Bureau de Conduite Centralisée — opérateur distribution (périmètre : son service)",
        [
            ("interruptions_distribution", "create"),
            ("interruptions_distribution", "read"),
            ("interruptions_distribution", "update"),
        ],
    ),
    (
        "BRC",
        "Bureau Régional de Conduite — opérateur régional distribution (périmètre : sa région)",
        [
            ("interruptions_distribution", "read"),
        ],
    ),
    (
        "DISPATCHER",
        "Opérateur réseau transport HTB — périmètre national transport",
        [
            ("interruptions_transport", "create"),
            ("interruptions_transport", "read"),
            ("interruptions_transport", "update"),
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
        ],
    ),
    (
        "ADMIN_SAQS",
        "Administrateur SAQS — lecture seule sur tout, jamais de création/modification",
        [
            ("interruptions_distribution", "read"),
            ("interruptions_transport", "read"),
            ("indicateurs", "read"),
            ("rapports", "read"),
            ("napt", "read"),
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
        ],
    ),
]


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------


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
    permission = result.scalar_one_or_none()
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
    result = await db.execute(select(Role).where(Role.nom == nom))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(nom=nom, description=description, is_active=True)
        db.add(role)
        await db.flush()
    return role


async def _upsert_role_permission(
    db: AsyncSession,
    role_id: int,
    permission_id: int,
) -> None:
    """Crée l'association role-permission si elle n'existe pas déjà."""
    result = await db.execute(
        select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        )
    )
    if result.scalar_one_or_none() is None:
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))


# ---------------------------------------------------------------------------
# Point d'entrée public
# ---------------------------------------------------------------------------


async def seed_rbac(db: AsyncSession) -> None:
    """Initialise les rôles et permissions RBAC du système SIR.

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
    for nom_role, description_role, role_perms in _ROLES:
        role = await _upsert_role(db, nom_role, description_role)

        for ressource, action in role_perms:
            permission = permission_map[(ressource, action)]
            await _upsert_role_permission(db, role.id, permission.id)

    # Flush final pour persister toutes les associations avant commit externe
    await db.flush()
