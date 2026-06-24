"""Helpers RBAC — rôle SUPERADMIN (dev uniquement)."""

from app.models.utilisateurs import Utilisateur

SUPERADMIN_ROLE = "SUPERADMIN"

# Rôles nationaux (hors SUPERADMIN)
NATIONAL_ROLES: frozenset[str] = frozenset(
    {"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS", "DISPATCHER", SUPERADMIN_ROLE}
)


def role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


def is_superadmin(user: Utilisateur) -> bool:
    return SUPERADMIN_ROLE in role_names(user)


def has_any_role(user: Utilisateur, roles: frozenset[str] | set[str]) -> bool:
    if is_superadmin(user):
        return True
    return bool(role_names(user).intersection(roles))
