from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.rapports import (
    RapportEnqueueResponse,
    RapportHebdoDDRequest,
    RapportHebdomadaireRequest,
    RapportJournalierRequest,
    RapportStatusResponse,
)
from app.services import rapport_generation_service

router = APIRouter()


@router.post(
    "/journalier",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander la génération d'un rapport journalier (async)",
)
async def post_rapport_journalier(
    body: RapportJournalierRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_journalier(db, current_user, body)
    return ApiResponse.success(result)


@router.post(
    "/hebdomadaire",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander le rapport hebdomadaire (lundi → dimanche, async)",
)
async def post_rapport_hebdomadaire(
    body: RapportHebdomadaireRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_hebdomadaire(db, current_user, body)
    return ApiResponse.success(result)


@router.post(
    "/hebdo-dd",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Rapport hebdomadaire d'exploitation DD (samedi → vendredi : Word, Excel, PDF)",
)
async def post_rapport_hebdo_dd(
    body: RapportHebdoDDRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_hebdo_dd(db, current_user, body)
    return ApiResponse.success(result)


@router.post(
    "/mensuel/distribution",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander la génération d'un rapport mensuel distribution (async)",
)
async def post_rapport_mensuel_distribution(
    annee: int = Query(..., ge=2000, le=2100),
    mois: int = Query(..., ge=1, le=12),
    region_id: int | None = Query(None, ge=1),
    limit: int = Query(10, ge=1, le=50, description="Top N feeders END"),
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_mensuel_distribution(
        db,
        current_user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        output_format=format,
        top_feeders_limit=limit,
    )
    return ApiResponse.success(result)


@router.post(
    "/mensuel/transport",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander la génération d'un rapport mensuel transport HTB (async)",
)
async def post_rapport_mensuel_transport(
    annee: int = Query(..., ge=2000, le=2100),
    mois: int = Query(..., ge=1, le=12),
    limit: int = Query(10, ge=1, le=50, description="Top N équipements END"),
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_mensuel_transport(
        db,
        current_user,
        annee=annee,
        mois=mois,
        output_format=format,
        top_equipements_limit=limit,
    )
    return ApiResponse.success(result)


@router.post(
    "/annuel",
    response_model=ApiResponse[RapportEnqueueResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Demander la génération d'un rapport annuel (async)",
)
async def post_rapport_annuel(
    annee: int = Query(..., ge=2000, le=2100),
    direction: str = Query(
        "distribution",
        pattern="^(distribution|transport|consolide)$",
    ),
    region_id: int | None = Query(None, ge=1),
    limit: int = Query(10, ge=1, le=50, description="Top N feeders/équipements END"),
    format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportEnqueueResponse]:
    result = await rapport_generation_service.enqueue_annuel(
        db,
        current_user,
        annee=annee,
        direction=direction,
        region_id=region_id,
        output_format=format,
        top_limit=limit,
    )
    return ApiResponse.success(result)


@router.get(
    "/{task_id}/status",
    response_model=ApiResponse[RapportStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Statut d'une génération de rapport",
)
async def get_rapport_status(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> ApiResponse[RapportStatusResponse]:
    result = await rapport_generation_service.get_status(db, current_user, task_id)
    return ApiResponse.success(result)


@router.get(
    "/{task_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Télécharger un rapport généré",
)
async def download_rapport(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("rapports", "read")),
) -> FileResponse:
    path, filename, media_type = await rapport_generation_service.resolve_download(
        db, current_user, task_id
    )
    return FileResponse(path, filename=filename, media_type=media_type)
