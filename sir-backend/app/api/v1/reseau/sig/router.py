from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.sig import TronconSigChaineResponse, TronconSigResponse
from app.services import sig_service

router = APIRouter()


@router.get(
    "/troncons",
    response_model=ApiResponse[PaginatedResponse[TronconSigResponse]],
    status_code=status.HTTP_200_OK,
    summary="Tronçons SIG d'un feeder",
)
async def list_troncons_sig(
    feeder_id: int = Query(..., ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TronconSigResponse]]:
    result = await sig_service.list_troncons_sig(
        db,
        current_user,
        feeder_id=feeder_id,
        page=page,
        page_size=page_size,
        search=search,
    )
    return ApiResponse.success(result)


@router.get(
    "/troncons/{troncon_sig_id}/chaine-aval",
    response_model=ApiResponse[TronconSigChaineResponse],
    status_code=status.HTTP_200_OK,
    summary="Chaîne aval SIG depuis un tronçon (3 traits legacy)",
)
async def get_chaine_aval_sig(
    troncon_sig_id: int,
    limit: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[TronconSigChaineResponse]:
    result = await sig_service.get_chaine_aval(
        db, current_user, troncon_sig_id, limit=limit
    )
    return ApiResponse.success(result)
