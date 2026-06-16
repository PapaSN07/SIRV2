from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.geo import (
    AgenceResponse,
    DelegationResponse,
    RegionResponse,
    ServiceResponse,
)
from app.services import geo_service

router = APIRouter()


@router.get(
    "/regions",
    response_model=ApiResponse[list[RegionResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des régions SENELEC",
)
async def list_regions(
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[list[RegionResponse]]:
    result = await geo_service.list_regions(db)
    return ApiResponse.success(result)


@router.get(
    "/delegations",
    response_model=ApiResponse[list[DelegationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des délégations d'une région",
)
async def list_delegations(
    region_id: int = Query(..., ge=1, description="Identifiant de la région"),
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[list[DelegationResponse]]:
    result = await geo_service.list_delegations(db, region_id)
    return ApiResponse.success(result)


@router.get(
    "/agences",
    response_model=ApiResponse[list[AgenceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des agences d'une délégation",
)
async def list_agences(
    delegation_id: int = Query(..., ge=1, description="Identifiant de la délégation"),
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[list[AgenceResponse]]:
    result = await geo_service.list_agences(db, delegation_id)
    return ApiResponse.success(result)


@router.get(
    "/services",
    response_model=ApiResponse[list[ServiceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des services d'une agence",
)
async def list_services(
    agence_id: int = Query(..., ge=1, description="Identifiant de l'agence"),
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[list[ServiceResponse]]:
    result = await geo_service.list_services(db, agence_id)
    return ApiResponse.success(result)
