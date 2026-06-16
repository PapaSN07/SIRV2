from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.reseau_transport import (
    EquipementTransportCreate,
    EquipementTransportResponse,
    EquipementTransportUpdate,
    PosteLigneCreate,
    PosteLigneResponse,
    PosteLigneUpdate,
    SourceTransportCreate,
    SourceTransportResponse,
    SourceTransportUpdate,
)
from app.services import reseau_transport_service as svc

router = APIRouter()


# ── Equipements transport ───────────────────────────────────────────────────


@router.get(
    "/equipements-transport",
    response_model=ApiResponse[PaginatedResponse[EquipementTransportResponse]],
    summary="Liste des équipements transport HTB",
)
async def list_equipements_transport(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_equipement: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[EquipementTransportResponse]]:
    result = await svc.list_resources(
        db,
        current_user,
        "equipements-transport",
        page,
        page_size,
        type_equipement=type_equipement,
    )
    return ApiResponse.success(result)


@router.get(
    "/equipements-transport/{item_id}",
    response_model=ApiResponse[EquipementTransportResponse],
)
async def get_equipement_transport(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[EquipementTransportResponse]:
    return ApiResponse.success(
        await svc.get_resource(db, current_user, "equipements-transport", item_id)
    )


@router.post(
    "/equipements-transport",
    response_model=ApiResponse[EquipementTransportResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer un équipement transport (Admin Dispatching)",
)
async def create_equipement_transport(
    body: EquipementTransportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[EquipementTransportResponse]:
    return ApiResponse.success(
        await svc.create_resource(db, current_user, "equipements-transport", body)
    )


@router.put(
    "/equipements-transport/{item_id}",
    response_model=ApiResponse[EquipementTransportResponse],
)
async def update_equipement_transport(
    item_id: int,
    body: EquipementTransportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[EquipementTransportResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "equipements-transport", item_id, body)
    )


@router.delete(
    "/equipements-transport/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_equipement_transport(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> None:
    await svc.delete_resource(db, current_user, "equipements-transport", item_id)


# ── Sources transport ───────────────────────────────────────────────────────


@router.get(
    "/sources-transport",
    response_model=ApiResponse[PaginatedResponse[SourceTransportResponse]],
    summary="Liste des sources transport",
)
async def list_sources_transport(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[SourceTransportResponse]]:
    result = await svc.list_resources(
        db, current_user, "sources-transport", page, page_size
    )
    return ApiResponse.success(result)


@router.get(
    "/sources-transport/{item_id}",
    response_model=ApiResponse[SourceTransportResponse],
)
async def get_source_transport(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[SourceTransportResponse]:
    return ApiResponse.success(
        await svc.get_resource(db, current_user, "sources-transport", item_id)
    )


@router.post(
    "/sources-transport",
    response_model=ApiResponse[SourceTransportResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_source_transport(
    body: SourceTransportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[SourceTransportResponse]:
    return ApiResponse.success(
        await svc.create_resource(db, current_user, "sources-transport", body)
    )


@router.put(
    "/sources-transport/{item_id}",
    response_model=ApiResponse[SourceTransportResponse],
)
async def update_source_transport(
    item_id: int,
    body: SourceTransportUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[SourceTransportResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "sources-transport", item_id, body)
    )


@router.delete(
    "/sources-transport/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source_transport(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> None:
    await svc.delete_resource(db, current_user, "sources-transport", item_id)


# ── Postes lignes ───────────────────────────────────────────────────────────


@router.get(
    "/postes-lignes",
    response_model=ApiResponse[PaginatedResponse[PosteLigneResponse]],
    summary="Liste des associations poste source ↔ ligne HTB",
)
async def list_postes_lignes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    poste_source_id: int | None = Query(default=None),
    equipement_transport_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PaginatedResponse[PosteLigneResponse]]:
    result = await svc.list_resources(
        db,
        current_user,
        "postes-lignes",
        page,
        page_size,
        poste_source_id=poste_source_id,
        equipement_transport_id=equipement_transport_id,
    )
    return ApiResponse.success(result)


@router.get(
    "/postes-lignes/{item_id}",
    response_model=ApiResponse[PosteLigneResponse],
)
async def get_poste_ligne(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
) -> ApiResponse[PosteLigneResponse]:
    return ApiResponse.success(
        await svc.get_resource(db, current_user, "postes-lignes", item_id)
    )


@router.post(
    "/postes-lignes",
    response_model=ApiResponse[PosteLigneResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_poste_ligne(
    body: PosteLigneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[PosteLigneResponse]:
    return ApiResponse.success(
        await svc.create_resource(db, current_user, "postes-lignes", body)
    )


@router.put(
    "/postes-lignes/{item_id}",
    response_model=ApiResponse[PosteLigneResponse],
)
async def update_poste_ligne(
    item_id: int,
    body: PosteLigneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> ApiResponse[PosteLigneResponse]:
    return ApiResponse.success(
        await svc.update_resource(db, current_user, "postes-lignes", item_id, body)
    )


@router.delete(
    "/postes-lignes/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_poste_ligne(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_DISPATCHING")),
) -> None:
    await svc.delete_resource(db, current_user, "postes-lignes", item_id)
