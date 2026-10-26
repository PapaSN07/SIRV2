import asyncio
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.utilisateurs import Utilisateur
from app.repositories import utilisateur_repository
from app.schemas.auth import LoginRequest, MeResponse
from app.services import ldap_service, login_throttle_service


# ---------------------------------------------------------------------------
# Constantes internes
# ---------------------------------------------------------------------------

_BLACKLIST_PREFIX = "jwt:blacklist:"
_REFRESH_PREFIX = "jwt:refresh:"  # stocke refresh_token_jti → user_id


# ---------------------------------------------------------------------------
# Helpers privés
# ---------------------------------------------------------------------------


def _blacklist_key(jti: str) -> str:
    return f"{_BLACKLIST_PREFIX}{jti}"


def _refresh_key(jti: str) -> str:
    return f"{_REFRESH_PREFIX}{jti}"


def _role_label(user: Utilisateur) -> str | None:
    """Retourne le premier rôle actif de l'utilisateur (le plus prioritaire)."""
    if not user.user_roles:
        return None
    return user.user_roles[0].role.nom


def _scope_service_id(user: Utilisateur) -> int | None:
    """Retourne le scope_service_id du premier user_role, ou None si national."""
    if not user.user_roles:
        return None
    return user.user_roles[0].scope_service_id


def _seconds_until_expiry(exp: int) -> int:
    """Calcule les secondes restantes avant expiration d'un token JWT."""
    remaining = exp - int(datetime.now(UTC).timestamp())
    return max(remaining, 0)


# ---------------------------------------------------------------------------
# Service public
# ---------------------------------------------------------------------------


async def _issue_tokens(db: AsyncSession, redis: Redis, user: Utilisateur) -> dict:
    """Émet access + refresh tokens pour un utilisateur actif."""
    access_jti = str(uuid.uuid4())
    refresh_jti = str(uuid.uuid4())

    extra_claims = {
        "role": _role_label(user),
        "service_id": _scope_service_id(user),
    }

    access_token = create_access_token(
        subject=str(user.id),
        jti=access_jti,
        extra=extra_claims,
    )
    refresh_token = create_refresh_token(
        subject=str(user.id),
        jti=refresh_jti,
    )

    refresh_ttl = settings.refresh_token_expire_days * 86400
    await redis.setex(_refresh_key(refresh_jti), refresh_ttl, str(user.id))

    return {
        "access_token": access_token,
        "expires_in": settings.access_token_expire_minutes * 60,
        "refresh_token": refresh_token,
        "user": user,
    }


async def login(
    db: AsyncSession,
    redis: Redis,
    body: LoginRequest,
) -> dict:
    """Authentifie l'utilisateur et retourne access_token + refresh_token.

    Raises:
        HTTPException 401 : identifiants incorrects (message volontairement générique).
        HTTPException 403 : utilisateur inactif ou première connexion forcée.
    """
    await login_throttle_service.ensure_not_locked(redis, body.login)

    user = await utilisateur_repository.get_by_login(db, body.login)

    # Compte présent dans l'AD : seul le mot de passe Active Directory est accepté.
    # None = annuaire inactif, compte absent ou injoignable → mot de passe local.
    # ldap3 est synchrone : exécuté dans un thread pour ne pas figer l'API.
    ad_ok = await asyncio.to_thread(ldap_service.verify_user_password, body.login, body.password)
    if ad_ok is True:
        password_ok = user is not None
    elif ad_ok is False:
        password_ok = False
    else:
        password_ok = user is not None and verify_password(body.password, user.password_hash)

    # Message générique : ne pas révéler si le login existe.
    if user is None or not password_ok:
        await login_throttle_service.register_failure(redis, body.login)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Identifiants invalides",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Compte désactivé. Contactez votre administrateur.",
            },
        )

    if ad_ok is True and user.premiere_connexion:
        await utilisateur_repository.update_premiere_connexion(db, user.id)
        await db.commit()
        user.premiere_connexion = False

    if user.premiere_connexion and ad_ok is not True:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": {
                    "code": "FORCE_PASSWORD_CHANGE",
                    "message": "Vous devez changer votre mot de passe avant de continuer.",
                },
            },
        )

    await login_throttle_service.reset(redis, body.login)
    return await _issue_tokens(db, redis, user)


async def change_password(
    db: AsyncSession,
    redis: Redis,
    login: str,
    current_password: str,
    new_password: str,
) -> dict:
    """Change le mot de passe lors de la première connexion et émet de nouveaux tokens."""
    await login_throttle_service.ensure_not_locked(redis, login)

    user = await utilisateur_repository.get_by_login(db, login)

    if user is None or not verify_password(current_password, user.password_hash):
        await login_throttle_service.register_failure(redis, login)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Identifiants invalides",
            },
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Compte désactivé. Contactez votre administrateur.",
            },
        )

    if not user.premiere_connexion:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Le changement de mot de passe n'est pas requis pour ce compte.",
            },
        )

    password_hash = hash_password(new_password)
    await utilisateur_repository.update_password(db, user.id, password_hash)
    await db.commit()

    user = await utilisateur_repository.get_by_id(db, user.id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "data": None,
                "error": "Erreur interne",
            },
        )

    return await _issue_tokens(db, redis, user)


async def refresh(
    db: AsyncSession,
    redis: Redis,
    refresh_token: str,
) -> dict:
    """Émet un nouvel access_token à partir d'un refresh_token valide.

    Raises:
        HTTPException 401 : refresh token invalide, expiré ou révoqué.
    """
    try:
        payload = decode_token(refresh_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Refresh token invalide ou expiré",
            },
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Token de mauvais type",
            },
        )

    refresh_jti: str = payload["jti"]
    user_id_str: str | None = await redis.get(_refresh_key(refresh_jti))

    if user_id_str is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Session expirée ou révoquée. Veuillez vous reconnecter.",
            },
        )

    user = await utilisateur_repository.get_by_id(db, int(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur introuvable ou désactivé",
            },
        )

    new_access_jti = str(uuid.uuid4())
    extra_claims = {
        "role": _role_label(user),
        "service_id": _scope_service_id(user),
    }
    access_token = create_access_token(
        subject=str(user.id),
        jti=new_access_jti,
        extra=extra_claims,
    )

    return {
        "access_token": access_token,
        "expires_in": settings.access_token_expire_minutes * 60,
    }


async def logout(
    redis: Redis,
    access_token_jti: str,
    access_token_exp: int,
    refresh_token: str | None = None,
) -> None:
    """Révoque l'access token et supprime le refresh token de Redis.

    Le JTI de l'access token est blacklisté avec un TTL égal au temps restant.
    """
    ttl = _seconds_until_expiry(access_token_exp)
    if ttl > 0:
        await redis.setex(_blacklist_key(access_token_jti), ttl, "1")

    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            refresh_jti = payload.get("jti")
            if refresh_jti:
                await redis.delete(_refresh_key(refresh_jti))
        except ValueError:
            # Refresh token déjà invalide — on ignore silencieusement
            pass


async def validate_access_token(redis: Redis, token: str) -> dict:
    """Vérifie signature, expiration, type et blacklist d'un access token.

    Returns:
        Le payload décodé.

    Raises:
        HTTPException 401 : token invalide, expiré, de mauvais type ou révoqué.
    """
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Token invalide ou expiré",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Token de mauvais type",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti: str = payload["jti"]

    # Vérification blacklist Redis
    is_blacklisted = await redis.exists(_blacklist_key(jti))
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Session révoquée. Veuillez vous reconnecter.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def get_current_user(
    db: AsyncSession,
    redis: Redis,
    token: str,
) -> Utilisateur:
    """Valide l'access token et retourne l'utilisateur authentifié.

    Raises:
        HTTPException 401 : token invalide, expiré ou blacklisté.
        HTTPException 403 : utilisateur inactif.
    """
    payload = await validate_access_token(redis, token)
    user_id = int(payload["sub"])
    user = await utilisateur_repository.get_by_id(db, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Utilisateur introuvable",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Compte désactivé",
            },
        )

    return user


def build_me_response(user: Utilisateur) -> MeResponse:
    """Construit la réponse /me à partir du modèle ORM."""
    return MeResponse(
        id=user.id,
        login=user.login,
        nom=user.nom,
        prenom=user.prenom,
        role_label=_role_label(user),
        service_id=_scope_service_id(user),
        premiere_connexion=user.premiere_connexion,
        is_active=user.is_active,
    )
