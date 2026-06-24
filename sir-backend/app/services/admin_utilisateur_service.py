"""Service métier — administration des utilisateurs (phase 1.5)."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import SUPERADMIN_ROLE, is_superadmin
from app.core.security import hash_password
from app.models.utilisateurs import Utilisateur
from app.repositories import admin_utilisateur_repository as admin_repo
from app.schemas.admin import (
    ResetPasswordRequest,
    RoleInfo,
    UtilisateurCreate,
    UtilisateurResponse,
    UtilisateurUpdate,
)
from app.schemas.common import PaginatedResponse
from app.utils.audit import ACTION_CREATE, ACTION_UPDATE, log_audit

# Rôles nationaux — scope_service_id doit être None
_NATIONAL_ROLES: frozenset[str] = frozenset(
    {"ADMIN_SCR", "ADMIN_DISPATCHING", "ADMIN_SAQS", "DISPATCHER", SUPERADMIN_ROLE}
)

# Rôles opérationnels — scope_service_id obligatoire
_SCOPED_ROLES: frozenset[str] = frozenset({"BCC", "BRC", "SUPERVISEUR"})


def _get_admin_direction(current_user: Utilisateur) -> str:
    """Détermine la direction admin de l'utilisateur connecté."""
    if is_superadmin(current_user):
        return "all"
    role_names = {ur.role.nom for ur in current_user.user_roles}
    if "ADMIN_SCR" in role_names:
        return "distribution"
    if "ADMIN_DISPATCHING" in role_names:
        return "transport"
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "status": "error",
            "data": None,
            "error": "Direction admin non reconnue",
        },
    )


def _build_response(user: Utilisateur) -> UtilisateurResponse:
    roles = [
        RoleInfo(
            role_id=ur.role_id,
            role_nom=ur.role.nom,
            scope_service_id=ur.scope_service_id,
        )
        for ur in user.user_roles
    ]
    return UtilisateurResponse(
        id=user.id,
        login=user.login,
        nom=user.nom,
        prenom=user.prenom,
        email=user.email,
        telephone=user.telephone,
        is_active=user.is_active,
        premiere_connexion=user.premiere_connexion,
        roles=roles,
    )


def _ensure_user_in_direction(user: Utilisateur, direction: str) -> None:
    """Vérifie que la cible appartient au périmètre de l'admin."""
    if direction == "all":
        return
    if not admin_repo.user_has_direction_role(user, direction):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur hors périmètre de votre direction",
            },
        )


async def _validate_role_assignments(
    db: AsyncSession,
    direction: str,
    assignments: list,
) -> list[tuple[int, int | None]]:
    """Valide et normalise les attributions de rôles."""
    allowed = None if direction == "all" else admin_repo.allowed_roles_for_direction(direction)
    normalized: list[tuple[int, int | None]] = []

    for assignment in assignments:
        role = await admin_repo.get_role_by_id(db, assignment.role_id)
        if role is None or not role.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Rôle id={assignment.role_id} introuvable ou inactif",
                },
            )

        if allowed is not None and role.nom not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Rôle '{role.nom}' non autorisé pour votre direction",
                },
            )

        scope = assignment.scope_service_id
        if role.nom in _NATIONAL_ROLES and scope is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Le rôle '{role.nom}' est national — scope_service_id doit être null",
                },
            )
        if role.nom in _SCOPED_ROLES and scope is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "status": "error",
                    "data": None,
                    "error": f"Le rôle '{role.nom}' requiert un scope_service_id",
                },
            )

        normalized.append((role.id, scope))

    return normalized


async def list_utilisateurs(
    db: AsyncSession,
    current_user: Utilisateur,
    page: int,
    page_size: int,
) -> PaginatedResponse[UtilisateurResponse]:
    direction = _get_admin_direction(current_user)
    if direction == "all":
        users, total = await admin_repo.list_all(db, page, page_size)
    else:
        users, total = await admin_repo.list_by_direction(db, direction, page, page_size)
    items = [_build_response(u) for u in users]
    return PaginatedResponse(
        items=items,
        total=total,
        page=max(1, page),
        page_size=max(1, min(page_size, 100)),
    )


async def create_utilisateur(
    db: AsyncSession,
    current_user: Utilisateur,
    body: UtilisateurCreate,
) -> UtilisateurResponse:
    direction = _get_admin_direction(current_user)

    existing = await admin_repo.get_by_login(db, body.login)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "error",
                "data": None,
                "error": f"Le login '{body.login}' est déjà utilisé",
            },
        )

    roles = await _validate_role_assignments(db, direction, body.roles)
    password_hash = hash_password(body.password)

    user = await admin_repo.create(
        db,
        login=body.login,
        password_hash=password_hash,
        nom=body.nom,
        prenom=body.prenom,
        email=body.email,
        telephone=body.telephone,
        roles=roles,
    )

    await log_audit(
        db,
        table_name="utilisateurs",
        record_id=user.id,
        action=ACTION_CREATE,
        user_id=current_user.id,
        new_values={"login": user.login, "roles": [r[0] for r in roles]},
    )

    return _build_response(user)


async def update_utilisateur(
    db: AsyncSession,
    current_user: Utilisateur,
    user_id: int,
    body: UtilisateurUpdate,
) -> UtilisateurResponse:
    direction = _get_admin_direction(current_user)

    user = await admin_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur introuvable",
            },
        )

    _ensure_user_in_direction(user, direction)

    old_values = {"nom": user.nom, "prenom": user.prenom}

    user = await admin_repo.update_profile(
        db,
        user,
        nom=body.nom,
        prenom=body.prenom,
        email=body.email,
        telephone=body.telephone,
    )

    if body.roles is not None:
        roles = await _validate_role_assignments(db, direction, body.roles)
        await admin_repo.replace_roles(db, user.id, roles)
        user = await admin_repo.get_by_id(db, user.id)
        assert user is not None

    await log_audit(
        db,
        table_name="utilisateurs",
        record_id=user.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values=old_values,
        new_values={"nom": user.nom, "prenom": user.prenom},
    )

    return _build_response(user)


async def activer_utilisateur(
    db: AsyncSession,
    current_user: Utilisateur,
    user_id: int,
) -> UtilisateurResponse:
    return await _set_active(db, current_user, user_id, is_active=True)


async def desactiver_utilisateur(
    db: AsyncSession,
    current_user: Utilisateur,
    user_id: int,
) -> UtilisateurResponse:
    return await _set_active(db, current_user, user_id, is_active=False)


async def _set_active(
    db: AsyncSession,
    current_user: Utilisateur,
    user_id: int,
    is_active: bool,
) -> UtilisateurResponse:
    direction = _get_admin_direction(current_user)

    user = await admin_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur introuvable",
            },
        )

    _ensure_user_in_direction(user, direction)

    if user.id == current_user.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Vous ne pouvez pas désactiver votre propre compte",
            },
        )

    old_active = user.is_active
    user = await admin_repo.set_active(db, user_id, is_active)
    assert user is not None

    await log_audit(
        db,
        table_name="utilisateurs",
        record_id=user.id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        old_values={"is_active": old_active},
        new_values={"is_active": is_active},
    )

    return _build_response(user)


async def reset_password(
    db: AsyncSession,
    current_user: Utilisateur,
    user_id: int,
    body: ResetPasswordRequest,
) -> None:
    direction = _get_admin_direction(current_user)

    user = await admin_repo.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur introuvable",
            },
        )

    _ensure_user_in_direction(user, direction)

    password_hash = hash_password(body.new_password)
    await admin_repo.reset_password(db, user_id, password_hash)

    await log_audit(
        db,
        table_name="utilisateurs",
        record_id=user_id,
        action=ACTION_UPDATE,
        user_id=current_user.id,
        new_values={"action": "reset_password"},
    )
