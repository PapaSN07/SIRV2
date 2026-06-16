from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.napt import (
    ConsignationCreate,
    ConsignationResponse,
    NaptCreate,
    NaptResponse,
    NaptUpdate,
)
from app.services import napt_service

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[NaptResponse]],
    status_code=status.HTTP_200_OK,
)
async def list_napt(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service_id: int | None = Query(None, ge=1),
    statut: str | None = Query(None),
    date_debut: datetime | None = Query(None),
    date_fin: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "read")),
) -> ApiResponse[PaginatedResponse[NaptResponse]]:
    result = await napt_service.list_items(
        db,
        current_user,
        page=page,
        page_size=page_size,
        service_id=service_id,
        statut=statut,
        date_debut=date_debut,
        date_fin=date_fin,
    )
    return ApiResponse.success(result)


@router.post(
    "",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_napt(
    body: NaptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "create")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.create(db, body, current_user)
    return ApiResponse.success(result)


@router.get(
    "/{napt_id}",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def get_napt(
    napt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "read")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.get_item(db, napt_id, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{napt_id}",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def update_napt(
    napt_id: int,
    body: NaptUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "update")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.update(db, napt_id, body, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{napt_id}/soumettre",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def soumettre_napt(
    napt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "update")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.soumettre(db, napt_id, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{napt_id}/valider",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def valider_napt(
    napt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "validate")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.valider(db, napt_id, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{napt_id}/executer",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def executer_napt(
    napt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "update")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.executer(db, napt_id, current_user)
    return ApiResponse.success(result)


@router.patch(
    "/{napt_id}/cloturer",
    response_model=ApiResponse[NaptResponse],
    status_code=status.HTTP_200_OK,
)
async def cloturer_napt(
    napt_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "update")),
) -> ApiResponse[NaptResponse]:
    result = await napt_service.cloturer(db, napt_id, current_user)
    return ApiResponse.success(result)


@router.post(
    "/{napt_id}/consignations",
    response_model=ApiResponse[ConsignationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_consignation(
    napt_id: int,
    body: ConsignationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("napt", "update")),
) -> ApiResponse[ConsignationResponse]:
    result = await napt_service.add_consignation(db, napt_id, body, current_user)
    return ApiResponse.success(result)
