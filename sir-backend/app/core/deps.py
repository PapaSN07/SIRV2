"""Dépendances FastAPI réutilisables — auth, RBAC, pagination."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.models.utilisateurs import Utilisateur
from app.services import auth_service

_bearer_scheme = HTTPBearer()

# Rôles dont le périmètre est national — pas de vérification de scope_service_id
_NATIONAL_ROLES: frozenset[str] = frozenset(
    {"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS", "DISPATCHER"}
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> Utilisateur:
    """Dépendance FastAPI : valide le Bearer token et retourne l'utilisateur authentifié.

    Vérifie la blacklist JTI dans Redis avant de retourner l'utilisateur.

    Usage dans un endpoint protégé :
        current_user: Utilisateur = Depends(get_current_user)
    """
    return await auth_service.get_current_user(db, redis, credentials.credentials)


def require_role(*roles: str):
    """Dépendance FastAPI : restreint l'accès aux rôles listés.

    Vérifie que l'utilisateur possède au moins un rôle parmi ceux listés.
    Un utilisateur multi-rôles est autorisé si l'un de ses rôles est dans la liste.

    Usage :
        current_user: Utilisateur = Depends(require_role("BCC", "BRC"))

    Raises:
        HTTPException 403 si aucun rôle de l'utilisateur n'est dans la liste.
    """

    async def _check(
        current_user: Utilisateur = Depends(get_current_user),
    ) -> Utilisateur:
        if not current_user.user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Aucun rôle assigné à ce compte",
                },
            )
        user_role_names = {ur.role.nom for ur in current_user.user_roles}
        if not user_role_names.intersection(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Rôle(s) requis : {', '.join(roles)}. Rôles actuels : {', '.join(sorted(user_role_names))}",
                },
            )
        return current_user

    return _check


def require_permission(resource: str, action: str):
    """Dépendance FastAPI : vérifie qu'un utilisateur a la permission resource:action.

    Parcourt les permissions issues de tous les rôles de l'utilisateur (déjà
    chargés eagerly par le repository — aucune requête SQL supplémentaire).

    Usage :
        Depends(require_permission("interruptions_distribution", "create"))

    Raises:
        HTTPException 403 si la permission est absente.
    """

    async def _check(
        current_user: Utilisateur = Depends(get_current_user),
    ) -> Utilisateur:
        for user_role in current_user.user_roles:
            for rp in user_role.role.role_permissions:
                perm = rp.permission
                if perm.ressource == resource and perm.action == action:
                    return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": f"Permission manquante : {resource}:{action}",
            },
        )

    return _check


def check_service_scope(current_user: Utilisateur, service_id: int) -> None:
    """Vérifie que l'utilisateur est autorisé à agir sur le service_id donné.

    Règles de scope appliquées :
    - Rôles nationaux (ADMIN_SCR, ADMIN_DISPATCHING, ADMIN_SAQS, DISPATCHER) :
      aucune restriction — toujours autorisé.
    - BCC : scope_service_id doit correspondre exactement au service_id de la ressource.
    - BRC / SUPERVISEUR : scope_service_id est utilisé comme filtre de service direct.
      La vérification de région doit être faite au niveau de la requête SQL
      (WHERE service.agence.delegation.region_id = :scope_region_id).

    Cette fonction doit être appelée dans la couche service, après la vérification
    du décorateur @require_permission sur le router (double enforcement RBAC).

    Args:
        current_user: Utilisateur authentifié chargé depuis get_current_user.
        service_id: Identifiant du service de la ressource cible.

    Raises:
        HTTPException 403 : si l'utilisateur tente d'accéder hors de son périmètre.
    """
    if not current_user.user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Aucun rôle assigné à ce compte",
            },
        )

    user_role_names = {ur.role.nom for ur in current_user.user_roles}

    # Les rôles nationaux n'ont pas de restriction de périmètre
    if user_role_names.intersection(_NATIONAL_ROLES):
        return

    # Pour BCC, BRC et SUPERVISEUR : le scope_service_id doit correspondre
    user_scope_service_id: int | None = current_user.user_roles[0].scope_service_id

    if user_scope_service_id is None:
        # scope_service_id non défini pour un rôle non-national : configuration invalide
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Périmètre de service non configuré pour ce compte",
            },
        )

    if user_scope_service_id != service_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Hors périmètre : service_id non autorisé",
            },
        )


def check_region_scope(current_user: Utilisateur, region_id: int) -> None:
    """Vérifie que l'utilisateur BRC est autorisé à agir sur la région donnée.

    Note : pour les BRC, le scope_service_id de user_roles stocke en réalité
    l'identifiant de région (scope régional). Cette convention est définie dans
    la modélisation des user_roles — le champ est nommé scope_service_id mais
    son interprétation dépend du rôle.

    TODO(RBAC): Si la modélisation évolue pour séparer scope_service_id et
    scope_region_id dans user_roles, mettre à jour cette fonction.

    Raises:
        HTTPException 403 : si le BRC tente d'accéder à une région hors périmètre.
    """
    if not current_user.user_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Aucun rôle assigné à ce compte",
            },
        )

    user_role_names = {ur.role.nom for ur in current_user.user_roles}

    if user_role_names.intersection(_NATIONAL_ROLES):
        return

    user_scope_id: int | None = current_user.user_roles[0].scope_service_id

    if user_scope_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Périmètre régional non configuré pour ce compte",
            },
        )

    if user_scope_id != region_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Hors périmètre : region_id non autorisé",
            },
        )
