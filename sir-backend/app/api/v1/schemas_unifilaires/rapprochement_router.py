"""Rapprochement Schéma unifilaire / SIG / SIR et postes à créer dans SIR.

Inclus avant le routeur des schémas : ses routes statiques (/postes-a-creer, /sig/noeuds) passent
avant /{schema_id}.
"""

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.utils.pagination import clamp_page_size
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse, PaginatedResponse
from app.schemas.schema_unifilaire import (
    AssociationPosteRequest,
    CompteursRapprochementResponse,
    LienSigRequest,
    LigneRapprochementResponse,
    NoeudSigCourtResponse,
    PosteACreerRequest,
    PosteACreerResponse,
    RapprochementSigResponse,
    RejetPosteRequest,
    StatutSirRequest,
    SuggestionCreationResponse,
    ValidationPosteRequest,
)
from app.services import schema_rapprochement_service as svc

router = APIRouter()
_LECTURE = require_permission("interruptions_distribution", "read")


@router.get("/postes-a-creer", response_model=ApiResponse[PaginatedResponse[PosteACreerResponse]])
async def lister_postes_a_creer(
    statut: str | None = Query(default="propose", pattern="^(propose|valide|rejete)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[PaginatedResponse[PosteACreerResponse]]:
    return ApiResponse.success(await svc.lister_demandes(db, statut, page, clamp_page_size(size)))


@router.post("/postes-a-creer/{demande_id}/valider", response_model=ApiResponse[PosteACreerResponse])
async def valider_poste_a_creer(
    body: ValidationPosteRequest,
    demande_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[PosteACreerResponse]:
    return ApiResponse.success(await svc.valider(db, demande_id, body.code, user))


@router.post("/postes-a-creer/{demande_id}/rejeter", response_model=ApiResponse[PosteACreerResponse])
async def rejeter_poste_a_creer(
    body: RejetPosteRequest,
    demande_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[PosteACreerResponse]:
    return ApiResponse.success(await svc.rejeter(db, demande_id, body.motif, user))


@router.get("/sig/noeuds", response_model=ApiResponse[list[NoeudSigCourtResponse]])
async def rechercher_noeuds_sig(
    q: str = Query(min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[list[NoeudSigCourtResponse]]:
    return ApiResponse.success(await svc.rechercher_sig(db, q))


@router.get("/{schema_id}/rapprochement", response_model=ApiResponse[PaginatedResponse[LigneRapprochementResponse]])
async def lignes_rapprochement(
    schema_id: int = Path(ge=1),
    filtre: str = Query(default="tous"),
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[PaginatedResponse[LigneRapprochementResponse]]:
    return ApiResponse.success(
        await svc.lignes(db, schema_id, filtre=filtre, recherche=q, page=page, page_size=clamp_page_size(size))
    )


@router.get("/{schema_id}/rapprochement/compteurs", response_model=ApiResponse[CompteursRapprochementResponse])
async def compteurs_rapprochement(
    schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[CompteursRapprochementResponse]:
    return ApiResponse.success(await svc.compteurs(db, schema_id))


@router.post("/{schema_id}/rapprochement/sig", response_model=ApiResponse[RapprochementSigResponse])
async def rapprocher_sig(
    schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[RapprochementSigResponse]:
    return ApiResponse.success(await svc.rapprocher_sig(db, schema_id, user))


@router.put("/{schema_id}/rapprochement/{poste_schema_id}/sig", response_model=ApiResponse[LigneRapprochementResponse])
async def lier_sig(
    body: LienSigRequest,
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[LigneRapprochementResponse]:
    return ApiResponse.success(await svc.lier_sig(db, schema_id, poste_schema_id, body.noeud_sig_id, user))


@router.put("/{schema_id}/rapprochement/{poste_schema_id}/sir", response_model=ApiResponse[LigneRapprochementResponse])
async def lier_sir(
    body: AssociationPosteRequest,
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[LigneRapprochementResponse]:
    return ApiResponse.success(await svc.lier_sir(db, schema_id, poste_schema_id, body.poste_id, user))


@router.put(
    "/{schema_id}/rapprochement/{poste_schema_id}/statut-sir", response_model=ApiResponse[LigneRapprochementResponse]
)
async def statut_sir(
    body: StatutSirRequest,
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[LigneRapprochementResponse]:
    return ApiResponse.success(await svc.definir_statut_sir(db, schema_id, poste_schema_id, body.statut_sir, user))


@router.get(
    "/{schema_id}/rapprochement/{poste_schema_id}/suggestion", response_model=ApiResponse[SuggestionCreationResponse]
)
async def suggestion_creation(
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    _user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[SuggestionCreationResponse]:
    return ApiResponse.success(await svc.suggestion_creation(db, schema_id, poste_schema_id))


@router.post("/{schema_id}/rapprochement/{poste_schema_id}/a-creer", response_model=ApiResponse[PosteACreerResponse])
async def proposer_creation(
    body: PosteACreerRequest,
    schema_id: int = Path(ge=1),
    poste_schema_id: int = Path(ge=1),
    db: AsyncSession = Depends(get_db),
    user: Utilisateur = Depends(_LECTURE),
) -> ApiResponse[PosteACreerResponse]:
    return ApiResponse.success(
        await svc.proposer(db, schema_id, poste_schema_id, body.libelle, body.feeder_id, user)
    )
