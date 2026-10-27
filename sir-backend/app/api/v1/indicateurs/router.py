from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.redis import get_redis
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.indicateurs import (
    EndIndicateurResponse,
    HistoriqueResponse,
    ObjectifsPilotageUpdate,
    PilotageResponse,
    SaidiIndicateurResponse,
    SaifiIndicateurResponse,
    TableauDeBordResponse,
    TendanceResponse,
    TopFeedersResponse,
)
from app.services import indicateurs_service, pilotage_service

router = APIRouter()


@router.get(
    "/end",
    response_model=ApiResponse[EndIndicateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Indicateur END agrégé pour une période",
)
async def get_end(
    annee: int = Query(..., ge=2000, le=2100),
    mois: int = Query(..., ge=1, le=12),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    include_services: bool = Query(False, description="Inclure le détail paginé par service"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[EndIndicateurResponse]:
    result = await indicateurs_service.get_end(
        db,
        redis,
        current_user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        page=page,
        page_size=page_size,
        include_services=include_services,
    )
    return ApiResponse.success(result)


@router.get(
    "/saifi",
    response_model=ApiResponse[SaifiIndicateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Indicateur SAIFI agrégé pour une période",
)
async def get_saifi(
    annee: int = Query(..., ge=2000, le=2100),
    mois: int = Query(..., ge=1, le=12),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    include_services: bool = Query(False, description="Inclure le détail paginé par service"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[SaifiIndicateurResponse]:
    result = await indicateurs_service.get_saifi(
        db,
        redis,
        current_user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        page=page,
        page_size=page_size,
        include_services=include_services,
    )
    return ApiResponse.success(result)


@router.get(
    "/saidi",
    response_model=ApiResponse[SaidiIndicateurResponse],
    status_code=status.HTTP_200_OK,
    summary="Indicateur SAIDI agrégé pour une période",
)
async def get_saidi(
    annee: int = Query(..., ge=2000, le=2100),
    mois: int = Query(..., ge=1, le=12),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    include_services: bool = Query(False, description="Inclure le détail paginé par service"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[SaidiIndicateurResponse]:
    result = await indicateurs_service.get_saidi(
        db,
        redis,
        current_user,
        annee=annee,
        mois=mois,
        region_id=region_id,
        page=page,
        page_size=page_size,
        include_services=include_services,
    )
    return ApiResponse.success(result)


@router.get(
    "/tableau-de-bord",
    response_model=ApiResponse[TableauDeBordResponse],
    status_code=status.HTTP_200_OK,
    summary="Tableau de bord indicateurs — KPI du mois",
)
async def get_tableau_de_bord(
    periode: str | None = Query(
        None,
        pattern=r"^\d{4}-\d{2}$",
        description="Période YYYY-MM (défaut : mois courant)",
    ),
    annee: int | None = Query(None, ge=2000, le=2100),
    mois: int | None = Query(None, ge=1, le=12),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[TableauDeBordResponse]:
    result = await indicateurs_service.get_tableau_de_bord(
        db,
        redis,
        current_user,
        periode=periode,
        annee=annee,
        mois=mois,
        region_id=region_id,
    )
    return ApiResponse.success(result)


@router.get(
    "/historique",
    response_model=ApiResponse[HistoriqueResponse],
    status_code=status.HTTP_200_OK,
    summary="Historique mensuel END / SAIFI / SAIDI",
)
async def get_historique(
    type: Literal["end", "saifi", "saidi"] = Query(..., description="Type d'indicateur"),
    annees: int = Query(1, ge=1, le=3, description="Nombre d'années (max 3)"),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    fin: str | None = Query(
        None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Dernier mois de la série (AAAA-MM)"
    ),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[HistoriqueResponse]:
    result = await indicateurs_service.get_historique(
        db,
        redis,
        current_user,
        indicateur_type=type,
        annees=annees,
        region_id=region_id,
        fin=fin,
    )
    return ApiResponse.success(result)


@router.get(
    "/top-feeders",
    response_model=ApiResponse[TopFeedersResponse],
    status_code=status.HTTP_200_OK,
    summary="Classement des feeders par END cumulée sur la période",
)
async def get_top_feeders(
    periode: str | None = Query(
        None,
        pattern=r"^\d{4}-\d{2}$",
        description="Période YYYY-MM (défaut : mois courant)",
    ),
    annee: int | None = Query(None, ge=2000, le=2100),
    mois: int | None = Query(None, ge=1, le=12),
    region_id: int | None = Query(None, ge=1, description="Région (admins nationaux)"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[TopFeedersResponse]:
    result = await indicateurs_service.get_top_feeders(
        db,
        redis,
        current_user,
        periode=periode,
        annee=annee,
        mois=mois,
        region_id=region_id,
        limit=limit,
    )
    return ApiResponse.success(result)


@router.get(
    "/pilotage",
    response_model=ApiResponse[PilotageResponse],
    status_code=status.HTTP_200_OK,
    summary="Objectifs, défauts aux 100 km, carte des postes ouverts et classements",
)
async def get_pilotage(
    periode: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    annee: int | None = Query(None, ge=2000, le=2100),
    mois: int | None = Query(None, ge=1, le=12),
    region_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[PilotageResponse]:
    result = await pilotage_service.get_pilotage(
        db,
        redis,
        current_user,
        periode=periode,
        annee=annee,
        mois=mois,
        region_id=region_id,
    )
    return ApiResponse.success(result)


@router.put(
    "/pilotage/objectifs",
    response_model=ApiResponse[PilotageResponse],
    status_code=status.HTTP_200_OK,
    summary="Enregistre les objectifs annuels END, SAIFI, SAIDI et défauts aux 100 km",
)
async def update_objectifs_pilotage(
    body: ObjectifsPilotageUpdate,
    region_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[PilotageResponse]:
    result = await pilotage_service.update_objectifs(
        db,
        redis,
        current_user,
        body,
        region_id=region_id,
    )
    return ApiResponse.success(result)


@router.get(
    "/pilotage/tendance",
    response_model=ApiResponse[TendanceResponse],
    status_code=status.HTTP_200_OK,
    summary="Courbe de tendance mensuelle d'un feeder ou d'un poste",
)
async def get_tendance_pilotage(
    cible: Literal["feeder", "poste"] = Query(...),
    cible_id: int = Query(..., ge=1),
    annees: int = Query(3, ge=2, le=3),
    region_id: int | None = Query(None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[TendanceResponse]:
    result = await pilotage_service.get_tendance(
        db,
        current_user,
        cible=cible,
        cible_id=cible_id,
        annees=annees,
        region_id=region_id,
    )
    return ApiResponse.success(result)
