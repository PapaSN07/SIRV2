"""Schémas unifilaires : visionneuse cliquable et postes entre deux postes."""

from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.schema_unifilaire import (
    AssociationPosteRequest,
    PosteSchemaResponse,
    PostesEntreRequest,
    PostesEntreResponse,
    SchemaUnifilaireResponse,
)
from app.services import schema_unifilaire_service as svc

router = APIRouter()

# Tuile blanche omise à l'import : réponse vide, le navigateur garde le fond blanc
_CACHE_TUILE = "private, max-age=86400"


@router.get("", response_model=ApiResponse[list[SchemaUnifilaireResponse]], summary="Schémas unifilaires importés")
async def lister_schemas(
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[list[SchemaUnifilaireResponse]]:
    return ApiResponse.success(await svc.lister(db))


@router.get("/{schema_id}", response_model=ApiResponse[SchemaUnifilaireResponse])
async def obtenir_schema(
    schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[SchemaUnifilaireResponse]:
    return ApiResponse.success(await svc.obtenir(db, schema_id))


@router.get(
    "/{schema_id}/postes",
    response_model=ApiResponse[list[PosteSchemaResponse]],
    summary="Postes cliquables du schéma, avec le poste SIRV2 rapproché",
)
async def postes_schema(
    schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[list[PosteSchemaResponse]]:
    return ApiResponse.success(await svc.postes(db, schema_id))


@router.get(
    "/{schema_id}/tuiles/{z}/{x}/{y}",
    summary="Tuile PNG 256 × 256 (Leaflet, CRS.Simple)",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}, 204: {"description": "Zone blanche"}},
)
async def tuile_schema(
    schema_id: int = Path(ge=1),
    z: int = Path(ge=0, le=12),
    x: int = Path(ge=0),
    y: int = Path(ge=0),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> Response:
    contenu = await svc.tuile(db, schema_id, z, x, y)
    if contenu is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": _CACHE_TUILE})
    return Response(content=contenu, media_type="image/png", headers={"Cache-Control": _CACHE_TUILE})


@router.post(
    "/{schema_id}/entre",
    response_model=ApiResponse[PostesEntreResponse],
    summary="Postes situés entre deux postes, le long des lignes du schéma",
)
async def postes_entre(
    body: PostesEntreRequest,
    schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[PostesEntreResponse]:
    return ApiResponse.success(await svc.entre(db, schema_id, body.debut_id, body.fin_id))


@router.put(
    "/{schema_id}/postes/{poste_schema_id}",
    response_model=ApiResponse[PosteSchemaResponse],
    summary="Associer un poste du schéma à un poste SIRV2 (Admin SCR)",
)
async def associer_poste(
    body: AssociationPosteRequest,
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(require_permission("interruptions_distribution", "read")),
) -> ApiResponse[PosteSchemaResponse]:
    return ApiResponse.success(await svc.associer(db, schema_id, poste_schema_id, body.poste_id, user))
