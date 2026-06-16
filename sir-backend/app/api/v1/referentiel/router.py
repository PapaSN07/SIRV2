from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.core.redis import get_redis
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.referentiel import ReferentielCreate, ReferentielResponse, ReferentielUpdate
from app.services import referentiel_service

router = APIRouter()


@router.get(
    "/{resource}",
    response_model=ApiResponse[PaginatedResponse[ReferentielResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée d'une ressource référentiel",
)
async def list_referentiel(
    resource: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_reseau: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[ReferentielResponse]]:
    result = await referentiel_service.list_items(
        db, redis, resource, page, page_size, type_reseau
    )
    return ApiResponse.success(result)


@router.get(
    "/{resource}/{item_id}",
    response_model=ApiResponse[ReferentielResponse],
    status_code=status.HTTP_200_OK,
    summary="Détail d'un élément référentiel",
)
async def get_referentiel(
    resource: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[ReferentielResponse]:
    result = await referentiel_service.get_item(db, resource, item_id)
    return ApiResponse.success(result)


@router.post(
    "/{resource}",
    response_model=ApiResponse[ReferentielResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un élément référentiel (Admin SCR / Admin Dispatching)",
)
async def create_referentiel(
    resource: str,
    body: ReferentielCreate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(
        require_role("ADMIN_SCR", "ADMIN_DISPATCHING")
    ),
) -> ApiResponse[ReferentielResponse]:
    result = await referentiel_service.create_item(
        db, redis, current_user, resource, body
    )
    return ApiResponse.success(result)


@router.put(
    "/{resource}/{item_id}",
    response_model=ApiResponse[ReferentielResponse],
    status_code=status.HTTP_200_OK,
    summary="Mettre à jour un élément référentiel",
)
async def update_referentiel(
    resource: str,
    item_id: int,
    body: ReferentielUpdate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(
        require_role("ADMIN_SCR", "ADMIN_DISPATCHING")
    ),
) -> ApiResponse[ReferentielResponse]:
    result = await referentiel_service.update_item(
        db, redis, current_user, resource, item_id, body
    )
    return ApiResponse.success(result)


@router.delete(
    "/{resource}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un élément référentiel (soft delete)",
)
async def delete_referentiel(
    resource: str,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(
        require_role("ADMIN_SCR", "ADMIN_DISPATCHING")
    ),
) -> None:
    await referentiel_service.delete_item(db, redis, current_user, resource, item_id)
