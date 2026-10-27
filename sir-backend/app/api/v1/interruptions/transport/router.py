from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.interruption_distribution import InterruptionClotureRequest
from app.schemas.interruption_statut import (
    ArchivageRequest,
    ArchivageResponse,
    MotifRequest,
    StatutHistoriqueResponse,
)
from app.schemas.interruption_transport import (
    InterruptionTransportCreate,
    InterruptionTransportDetailResponse,
    InterruptionTransportResponse,
    InterruptionTransportUpdate,
    StatutInterruption,
    TypeDirectionTransport,
)
from app.services import interruption_transport_service

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[InterruptionTransportResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste paginée des interruptions transport / OMVG",
)
async def list_interruptions_transport(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_direction: TypeDirectionTransport | None = Query(default=None),
    statut: StatutInterruption | None = Query(default=None),
    date_debut: datetime | None = Query(default=None),
    date_fin: datetime | None = Query(default=None),
    equipement_transport_id: int | None = Query(default=None, ge=1),
    source_transport_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "read")
    ),
) -> ApiResponse[PaginatedResponse[InterruptionTransportResponse]]:
    result = await interruption_transport_service.list_items(
        db,
        current_user,
        page=page,
        page_size=page_size,
        type_direction=type_direction,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
        equipement_transport_id=equipement_transport_id,
        source_transport_id=source_transport_id,
    )
    return ApiResponse.success(result)


@router.post(
    "/archiver",
    response_model=ApiResponse[ArchivageResponse],
    status_code=status.HTTP_200_OK,
    summary="Archiver (geler) les interruptions transport/OMVG validées d'un mois",
)
async def archiver_mois_transport(
    body: ArchivageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_transport", "validate")),
) -> ApiResponse[ArchivageResponse]:
    result = await interruption_transport_service.archiver_mois(db, body, current_user)
    return ApiResponse.success(result)


@router.post(
    "",
    response_model=ApiResponse[InterruptionTransportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer une interruption transport ou OMVG",
)
async def create_interruption_transport(
    body: InterruptionTransportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "create")
    ),
) -> ApiResponse[InterruptionTransportResponse]:
    result = await interruption_transport_service.create(db, body, current_user)
    return ApiResponse.success(result)


@router.put(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionTransportResponse],
    status_code=status.HTTP_200_OK,
    summary="Modifier une interruption transport ou OMVG",
)
async def update_interruption_transport(
    interruption_id: int,
    body: InterruptionTransportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "update")
    ),
) -> ApiResponse[InterruptionTransportResponse]:
    result = await interruption_transport_service.update(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/cloturer",
    response_model=ApiResponse[InterruptionTransportResponse],
    status_code=status.HTTP_200_OK,
    summary="Clôturer une interruption transport ou OMVG",
)
async def cloturer_interruption_transport(
    interruption_id: int,
    body: InterruptionClotureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "update")
    ),
) -> ApiResponse[InterruptionTransportResponse]:
    result = await interruption_transport_service.cloturer(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}/historique-statuts",
    response_model=ApiResponse[list[StatutHistoriqueResponse]],
    status_code=status.HTTP_200_OK,
    summary="Historique des statuts d'une interruption transport",
)
async def historique_statuts_transport(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_transport", "read")),
) -> ApiResponse[list[StatutHistoriqueResponse]]:
    result = await interruption_transport_service.historique_statuts(db, interruption_id, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/renvoyer",
    response_model=ApiResponse[InterruptionTransportDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Renvoyer en correction (Admin Dispatching, motif obligatoire)",
)
async def renvoyer_interruption_transport(
    interruption_id: int,
    body: MotifRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_transport", "validate")),
) -> ApiResponse[InterruptionTransportDetailResponse]:
    result = await interruption_transport_service.renvoyer_en_correction(
        db, interruption_id, body, current_user
    )
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/devalider",
    response_model=ApiResponse[InterruptionTransportDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Dévalider (Admin Dispatching, motif obligatoire)",
)
async def devalider_interruption_transport(
    interruption_id: int,
    body: MotifRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("interruptions_transport", "validate")),
) -> ApiResponse[InterruptionTransportDetailResponse]:
    result = await interruption_transport_service.devalider(db, interruption_id, body, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{interruption_id}/valider",
    response_model=ApiResponse[InterruptionTransportResponse],
    status_code=status.HTTP_200_OK,
    summary="Valider une interruption transport ou OMVG clôturée",
)
async def valider_interruption_transport(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "validate")
    ),
) -> ApiResponse[InterruptionTransportResponse]:
    result = await interruption_transport_service.valider(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)


@router.get(
    "/{interruption_id}",
    response_model=ApiResponse[InterruptionTransportDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Détail d'une interruption transport ou OMVG",
)
async def get_interruption_transport(
    interruption_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(
        require_permission("interruptions_transport", "read")
    ),
) -> ApiResponse[InterruptionTransportDetailResponse]:
    result = await interruption_transport_service.get_item(
        db, interruption_id, current_user
    )
    return ApiResponse.success(result)
