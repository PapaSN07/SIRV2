from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis
from app.core.deps import get_current_user
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.sig import (
    Defauts100KmResponse,
    FeederSigResponse,
    NoeudSigAdminResponse,
    StationSigResponse,
    SyntheseSigResponse,
    TronconSigAdminResponse,
    TronconSigChaineResponse,
    TronconSigResponse,
)
from app.services import sig_admin_service, sig_service

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
    page_size: int = Query(50, ge=1, le=500),
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


# ── Administration → SIG (consultation, lecture seule) ──────────────────────────
# Routes statiques « /admin/… » : déclarées avant toute route dynamique de ce routeur.

_Q = Query(default=None, max_length=100, description="Recherche (chaque mot, sans casse)")


@router.get("/admin/synthese", response_model=ApiResponse[SyntheseSigResponse], summary="Synthèse de la topologie SIG")
async def synthese_sig(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[SyntheseSigResponse]:
    return ApiResponse.success(await sig_admin_service.synthese(db, current_user, redis))


@router.get(
    "/admin/stations",
    response_model=ApiResponse[PaginatedResponse[StationSigResponse]],
    summary="Stations (postes sources) du SIG",
)
async def stations_sig(
    q: str | None = _Q,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[StationSigResponse]]:
    return ApiResponse.success(
        await sig_admin_service.stations(db, current_user, recherche=q, page=page, page_size=page_size, redis=redis)
    )


@router.get(
    "/admin/feeders",
    response_model=ApiResponse[PaginatedResponse[FeederSigResponse]],
    summary="Départs du SIG et rattachement aux feeders SIRV2",
)
async def feeders_sig(
    q: str | None = _Q,
    rattachement: Literal["rattache", "non_rattache"] | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[FeederSigResponse]]:
    return ApiResponse.success(
        await sig_admin_service.feeders(
            db, current_user, recherche=q, rattachement=rattachement, page=page, page_size=page_size, redis=redis
        )
    )


@router.get(
    "/admin/troncons",
    response_model=ApiResponse[PaginatedResponse[TronconSigAdminResponse]],
    summary="Tronçons SIG (dernier chargement)",
)
async def troncons_sig_admin(
    q: str | None = _Q,
    nom_feeder: str | None = Query(default=None, max_length=255),
    tri: str | None = Query(default=None, pattern=r"^-?(nom_troncon|nom_feeder|longueur_m|tension_kv)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TronconSigAdminResponse]]:
    return ApiResponse.success(
        await sig_admin_service.troncons(
            db, current_user, recherche=q, nom_feeder=nom_feeder, tri=tri, page=page, page_size=page_size
        )
    )


@router.get(
    "/admin/noeuds",
    response_model=ApiResponse[PaginatedResponse[NoeudSigAdminResponse]],
    summary="Nœuds SIG avec coordonnées (UTM 28N et WGS84)",
)
async def noeuds_sig_admin(
    q: str | None = _Q,
    nom_feeder: str | None = Query(default=None, max_length=255),
    station: str | None = Query(default=None, max_length=255),
    categorie: str | None = Query(default=None, max_length=255),
    localisation: Literal["localise", "non_localise"] | None = Query(default=None),
    tri: str | None = Query(default=None, pattern=r"^-?(nom|nom_feeder|station|categorie)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[NoeudSigAdminResponse]]:
    return ApiResponse.success(
        await sig_admin_service.noeuds(
            db,
            current_user,
            recherche=q,
            nom_feeder=nom_feeder,
            station=station,
            categorie=categorie,
            localisation=localisation,
            tri=tri,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/admin/carte",
    response_model=ApiResponse[list[NoeudSigAdminResponse]],
    summary="Nœuds localisés d'un départ ou d'une station (carte)",
)
async def carte_sig(
    nom_feeder: str | None = Query(default=None, max_length=255),
    station: str | None = Query(default=None, max_length=255),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[list[NoeudSigAdminResponse]]:
    return ApiResponse.success(
        await sig_admin_service.carte(db, current_user, nom_feeder=nom_feeder, station=station)
    )


@router.get(
    "/admin/defauts-100km",
    response_model=ApiResponse[Defauts100KmResponse],
    response_model_by_alias=True,
    summary="Défauts aux 100 km : global, par service, par feeder SIG, par nature",
)
async def defauts_100km_sig(
    annee: int | None = Query(default=None, ge=2000, le=2100),
    mois: int | None = Query(default=None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[Defauts100KmResponse]:
    return ApiResponse.success(
        await sig_admin_service.defauts_100km(db, current_user, annee=annee, mois=mois, redis=redis)
    )
