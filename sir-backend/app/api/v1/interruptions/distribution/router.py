from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.interruption_distribution import (
    InterruptionDistributionCreate,
    InterruptionClotureRequest,
    InterruptionDistributionDetailResponse,
    InterruptionDistributionResponse,
    InterruptionDistributionUpdate,
    PosteImpacteResponse,
    PosteInterruptionCreate,
    StatutInterruption,
)
from app.services import interruption_distribution_service

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[InterruptionDistributionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée des interruptions distribution",
)
async def list_interruptions_distribution(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    region_id: int | None = Query(default=None, ge=1),
    feeder_id: int | None = Query(default=None, ge=1),
    statut: StatutInterruption | None = Query(default=None),
    date_debut: datetime | None = Query(default=None),
    date_fin: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[PaginatedResponse[InterruptionDistributionResponse]]:
    result = await interruption_distribution_service.list_items(
        db,
        current_user,
        page=page,
        page_size=page_size,
        region_id=region_id,
        feeder_id=feeder_id,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.post(
    "",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer une interruption distribution",
)
async def create_interruption_distribution(
    body: InterruptionDistributionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "create")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.create(db, body, current_user)
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}/postes",
    response_model=ApiResponse[list[PosteImpacteResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des postes impactés par une interruption",
)
async def list_postes_interruption(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[list[PosteImpacteResponse]]:
    result = await interruption_distribution_service.list_postes(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.post(
    "/{interruption_id}/postes",
    response_model=ApiResponse[PosteImpacteResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Associer un poste impacté à une interruption",
)
async def add_poste_interruption(
    interruption_id: int,
    body: PosteInterruptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[PosteImpacteResponse]:
    result = await interruption_distribution_service.add_poste(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.delete(
    "/{interruption_id}/postes/{poste_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Retirer un poste impacté d'une interruption",
)
async def remove_poste_interruption(
    interruption_id: int,
    poste_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> Response:
    await interruption_distribution_service.remove_poste(
        db, interruption_id, poste_id, current_user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Modifier une interruption distribution",
)
async def update_interruption_distribution(
    interruption_id: int,
    body: InterruptionDistributionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.update(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/cloturer",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Clôturer une interruption distribution",
)
async def cloturer_interruption_distribution(
    interruption_id: int,
    body: InterruptionClotureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "update")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.cloturer(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/valider",
    response_model=ApiResponse[InterruptionDistributionResponse],
    status_code=status.HTTP_200_OK,
    summary="Valider une interruption distribution clôturée",
)
async def valider_interruption_distribution(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "validate")
    ),
) -> ApiResponse[InterruptionDistributionResponse]:
    result = await interruption_distribution_service.valider(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionDistributionDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Détail d'une interruption distribution",
)
async def get_interruption_distribution(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_distribution", "read")
    ),
) -> ApiResponse[InterruptionDistributionDetailResponse]:
    result = await interruption_distribution_service.get_item(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)
