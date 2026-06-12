from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_token
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter()

_bearer_scheme = HTTPBearer()

# TTL du cookie refresh token en secondes
_REFRESH_COOKIE_MAX_AGE = settings.refresh_token_expire_days * 86400
_REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Pose le cookie HttpOnly contenant le refresh token."""
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=_REFRESH_COOKIE_MAX_AGE,
        path="/api/v1/auth",
    )


def _delete_refresh_cookie(response: Response) -> None:
    """Supprime le cookie refresh token."""
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path="/api/v1/auth",
    )


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Authentification — retourne un access token JWT",
)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse[TokenResponse]:
    """Authentifie l'utilisateur avec login + mot de passe.

    - Retourne un access token dans le body de réponse.
    - Pose un cookie HttpOnly `refresh_token`.
    - Lève 401 si les identifiants sont incorrects.
    - Lève 403 si le compte est désactivé ou si première connexion (FORCE_PASSWORD_CHANGE).
    """
    result = await auth_service.login(db, redis, body)

    _set_refresh_cookie(response, result["refresh_token"])

    token_data = TokenResponse(
        access_token=result["access_token"],
        expires_in=result["expires_in"],
    )
    return ApiResponse.success(token_data)


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenResponse],
    status_code=status.HTTP_200_OK,
    summary="Renouvellement de l'access token via le cookie refresh",
)
async def refresh(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> ApiResponse[TokenResponse]:
    """Émet un nouvel access token à partir du cookie refresh_token.

    - Lève 401 si le cookie est absent, invalide, expiré ou révoqué.
    """
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Cookie refresh_token absent. Veuillez vous reconnecter.",
            },
        )

    result = await auth_service.refresh(db, redis, refresh_token)

    token_data = TokenResponse(
        access_token=result["access_token"],
        expires_in=result["expires_in"],
    )
    return ApiResponse.success(token_data)


# ---------------------------------------------------------------------------
# DELETE /logout
# ---------------------------------------------------------------------------


@router.delete(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Révocation du token et suppression du cookie refresh",
)
async def logout(
    response: Response,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    redis: Redis = Depends(get_redis),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE_NAME),
) -> None:
    """Révoque l'access token (blacklist JTI Redis) et supprime le cookie refresh.

    - Lève 401 si l'access token est absent ou invalide.
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "status": "error",
                "data": None,
                "error": "Token invalide",
            },
        )

    access_jti: str = payload["jti"]
    access_exp: int = payload["exp"]

    await auth_service.logout(
        redis=redis,
        access_token_jti=access_jti,
        access_token_exp=access_exp,
        refresh_token=refresh_token,
    )

    _delete_refresh_cookie(response)


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=ApiResponse[MeResponse],
    status_code=status.HTTP_200_OK,
    summary="Profil de l'utilisateur authentifié",
)
async def me(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ApiResponse[MeResponse]:
    """Retourne le profil de l'utilisateur identifié par son access token.

    - Lève 401 si le token est absent, invalide, expiré ou blacklisté.
    - Lève 403 si le compte est désactivé.
    """
    token = credentials.credentials
    user = await auth_service.get_current_user(db, redis, token)
    return ApiResponse.success(auth_service.build_me_response(user))
