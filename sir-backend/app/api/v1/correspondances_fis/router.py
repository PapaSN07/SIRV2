"""Correspondances FIS administrées : libellé du fichier FIS → entrée du Référentiel.

Lecture : `interruptions_distribution:read` (écran d'import, BCC compris).
Création / suppression : Admin SCR (et SUPERADMIN), droits du Référentiel distribution contrôlés
par le service.
"""

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission, require_role
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.correspondance_fis import CategorieFis, CorrespondanceFisCreate, CorrespondanceFisResponse
from app.services import correspondance_fis_service

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[list[CorrespondanceFisResponse]],
    status_code=status.HTTP_200_OK,
    summary="Liste des correspondances FIS (filtre facultatif par catégorie)",
)
async def lister_correspondances(
    categorie: CategorieFis | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _current_user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[list[CorrespondanceFisResponse]]:
    result = await correspondance_fis_service.lister(db, categorie=categorie)
    return ApiResponse.success(result)


@router.post(
    "",
    response_model=ApiResponse[CorrespondanceFisResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Créer une correspondance FIS (Admin SCR)",
)
async def creer_correspondance(
    body: CorrespondanceFisCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[CorrespondanceFisResponse]:
    result = await correspondance_fis_service.creer(db, current_user=current_user, body=body)
    return ApiResponse.success(result)


@router.delete(
    "/{correspondance_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Supprimer une correspondance FIS (Admin SCR)",
)
async def supprimer_correspondance(
    correspondance_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_role("ADMIN_SCR")),
) -> ApiResponse[None]:
    await correspondance_fis_service.supprimer(db, current_user=current_user, correspondance_id=correspondance_id)
    return ApiResponse.success(None)
