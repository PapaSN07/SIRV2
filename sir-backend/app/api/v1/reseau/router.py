from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.reseau_distribution import (
    FeederCreate,
    FeederResponse,
    FeederUpdate,
    PosteCreate,
    PosteResponse,
    PosteSourceCreate,
    PosteSourceResponse,
    PosteSourceUpdate,
    PosteUpdate,
    SousFeederCreate,
    SousFeederResponse,
    SousFeederUpdate,
    TronconCreate,
    TronconResponse,
    TronconUpdate,
)
from app.services import reseau_distribution_service as svc

router = APIRouter()


# ── Postes sources ──────────────────────────────────────────────────────────


@router.get(
    "/postes-sources",
    response_model=ApiResponse[PaginatedResponse[PosteSourceResponse]],
    summary="Liste des postes sources",
)
async def list_postes_sources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    region_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[PosteSourceResponse]]:
    result = await svc.list_resources(
        db, current_user, "postes-sources", page, page_size, region_id=region_id
    )
    return ApiResponse.success(result)


@router.get(
    "/postes-sources/{item_id}",
    response_model=ApiResponse[PosteSourceResponse],
    summary="Détail poste source",
)
async def get_poste_source(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PosteSourceResponse]:
    return ApiResponse.success(await svc.get_resource(db, current_user, "postes-sources", item_id))


@router.post(
    "/postes-sources",
    response_model=ApiResponse[PosteSourceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un poste source (Admin SCR)",
)
async def create_poste_source(
    body: PosteSourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[PosteSourceResponse]:
    return ApiResponse.success(await svc.create_resource(db, current_user, "postes-sources", body))


@router.put(
    "/postes-sources/{item_id}",
    response_model=ApiResponse[PosteSourceResponse],
    summary="Mettre à jour un poste source",
)
async def update_poste_source(
    item_id: int,
    body: PosteSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[PosteSourceResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "postes-sources", item_id, body)
    )


@router.delete(
    "/postes-sources/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un poste source",
)
async def delete_poste_source(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> None:
    await svc.delete_resource(db, current_user, "postes-sources", item_id)


# ── Feeders ─────────────────────────────────────────────────────────────────


@router.get(
    "/feeders",
    response_model=ApiResponse[PaginatedResponse[FeederResponse]],
    summary="Liste des feeders",
)
async def list_feeders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    poste_source_id: int | None = Query(default=None),
    service_id: int | None = Query(default=None),
    region_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[FeederResponse]]:
    result = await svc.list_resources(
        db,
        current_user,
        "feeders",
        page,
        page_size,
        poste_source_id=poste_source_id,
        service_id=service_id,
        region_id=region_id,
    )
    return ApiResponse.success(result)


@router.get(
    "/feeders/{item_id}",
    response_model=ApiResponse[FeederResponse],
    summary="Détail feeder",
)
async def get_feeder(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[FeederResponse]:
    return ApiResponse.success(await svc.get_resource(db, current_user, "feeders", item_id))


@router.post(
    "/feeders",
    response_model=ApiResponse[FeederResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un feeder (Admin SCR)",
)
async def create_feeder(
    body: FeederCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[FeederResponse]:
    return ApiResponse.success(await svc.create_resource(db, current_user, "feeders", body))


@router.put(
    "/feeders/{item_id}",
    response_model=ApiResponse[FeederResponse],
    summary="Mettre à jour un feeder",
)
async def update_feeder(
    item_id: int,
    body: FeederUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[FeederResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "feeders", item_id, body)
    )


@router.delete(
    "/feeders/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Désactiver un feeder",
)
async def delete_feeder(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> None:
    await svc.delete_resource(db, current_user, "feeders", item_id)


# ── Postes ──────────────────────────────────────────────────────────────────


@router.get(
    "/postes",
    response_model=ApiResponse[PaginatedResponse[PosteResponse]],
    summary="Liste des postes MT/BT",
)
async def list_postes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feeder_id: int | None = Query(default=None),
    service_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[PosteResponse]]:
    result = await svc.list_resources(
        db,
        current_user,
        "postes",
        page,
        page_size,
        feeder_id=feeder_id,
        service_id=service_id,
    )
    return ApiResponse.success(result)


@router.get("/postes/{item_id}", response_model=ApiResponse[PosteResponse])
async def get_poste(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PosteResponse]:
    return ApiResponse.success(await svc.get_resource(db, current_user, "postes", item_id))


@router.post(
    "/postes",
    response_model=ApiResponse[PosteResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_poste(
    body: PosteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[PosteResponse]:
    return ApiResponse.success(await svc.create_resource(db, current_user, "postes", body))


@router.put("/postes/{item_id}", response_model=ApiResponse[PosteResponse])
async def update_poste(
    item_id: int,
    body: PosteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[PosteResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "postes", item_id, body)
    )


@router.delete("/postes/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_poste(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> None:
    await svc.delete_resource(db, current_user, "postes", item_id)


# ── Tronçons ──────────────────────────────────────────────────────────────────


@router.get(
    "/troncons",
    response_model=ApiResponse[PaginatedResponse[TronconResponse]],
    summary="Liste des tronçons",
)
async def list_troncons(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feeder_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[TronconResponse]]:
    result = await svc.list_resources(
        db, current_user, "troncons", page, page_size, feeder_id=feeder_id
    )
    return ApiResponse.success(result)


@router.get("/troncons/{item_id}", response_model=ApiResponse[TronconResponse])
async def get_troncon(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[TronconResponse]:
    return ApiResponse.success(await svc.get_resource(db, current_user, "troncons", item_id))


@router.post(
    "/troncons",
    response_model=ApiResponse[TronconResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_troncon(
    body: TronconCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[TronconResponse]:
    return ApiResponse.success(await svc.create_resource(db, current_user, "troncons", body))


@router.put("/troncons/{item_id}", response_model=ApiResponse[TronconResponse])
async def update_troncon(
    item_id: int,
    body: TronconUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[TronconResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "troncons", item_id, body)
    )


@router.delete("/troncons/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_troncon(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> None:
    await svc.delete_resource(db, current_user, "troncons", item_id)


# ── Sous-feeders ────────────────────────────────────────────────────────────


@router.get(
    "/sous-feeders",
    response_model=ApiResponse[PaginatedResponse[SousFeederResponse]],
    summary="Liste des sous-feeders",
)
async def list_sous_feeders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    feeder_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[SousFeederResponse]]:
    result = await svc.list_resources(
        db, current_user, "sous-feeders", page, page_size, feeder_id=feeder_id
    )
    return ApiResponse.success(result)


@router.get("/sous-feeders/{item_id}", response_model=ApiResponse[SousFeederResponse])
async def get_sous_feeder(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[SousFeederResponse]:
    return ApiResponse.success(
        await svc.get_resource(db, current_user, "sous-feeders", item_id)
    )


@router.post(
    "/sous-feeders",
    response_model=ApiResponse[SousFeederResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_sous_feeder(
    body: SousFeederCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[SousFeederResponse]:
    return ApiResponse.success(
        await svc.create_resource(db, current_user, "sous-feeders", body)
    )


@router.put("/sous-feeders/{item_id}", response_model=ApiResponse[SousFeederResponse])
async def update_sous_feeder(
    item_id: int,
    body: SousFeederUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[SousFeederResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "sous-feeders", item_id, body)
    )


@router.delete("/sous-feeders/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sous_feeder(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> None:
    await svc.delete_resource(db, current_user, "sous-feeders", item_id)


# ── Topologie SIG (phase C) ─────────────────────────────────────────────────

from app.api.v1.reseau.sig.router import router as sig_reseau_router

router.include_router(sig_reseau_router, prefix="/sig", tags=["sig"])

# ── Réseau transport HTB (phase 2.4) ────────────────────────────────────────

from app.api.v1.reseau.transport.router import router as transport_reseau_router

router.include_router(transport_reseau_router, prefix="/transport")
