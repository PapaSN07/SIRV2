"""Base clients SAIFI/SAIDI : contrats par unité de relève (BI_ODS ou fichier H2MC mensuel)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.base_clients import (
    ActionAtelier,
    BaseClientsResume,
    DroitsAtelier,
    LienPosteUR,
    LienPosteURCreate,
    PosteRecherche,
    TacheLancee,
    UniteReleveRecherche,
)
from app.schemas.common import ApiResponse, PaginatedResponse
from app.services import atelier_clients_service as atelier
from app.services import base_clients_service as svc

router = APIRouter()


def _erreur(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"status": "error", "data": None, "error": message})


def _verifier_admin(user: Utilisateur) -> None:
    if not svc.peut_administrer(user):
        raise _erreur(status.HTTP_403_FORBIDDEN, "Réservé à l'administration SCR et au SAQS")


@router.get(
    "/contrats",
    response_model=ApiResponse[BaseClientsResume],
    summary="Mois chargés (contrats par unité de relève) et liens poste ↔ UR",
)
async def resume_contrats(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[BaseClientsResume]:
    return ApiResponse.success(BaseClientsResume(**await svc.resume(db)))


@router.post(
    "/contrats/synchroniser",
    response_model=ApiResponse[TacheLancee],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Relire BI_ODS.CONTRATS_PAR_AGENCE_UR et recalculer les clients",
)
async def synchroniser_contrats(
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[TacheLancee]:
    _verifier_admin(current_user)
    try:
        task_id = svc.lancer_synchronisation()
    except svc.BaseClientsErreur as exc:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ApiResponse.success(TacheLancee(task_id=task_id, message="Synchronisation lancée"))


@router.post(
    "/contrats/import",
    response_model=ApiResponse[TacheLancee],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Importer le fichier mensuel nombredeclientsh2mc_MMAAAA.xlsx",
)
async def importer_contrats(
    annee: int = Form(..., ge=2000, le=2100),
    mois: int = Form(..., ge=1, le=12),
    fichier: UploadFile = File(..., description="Fichier H2MC (.xlsx)"),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[TacheLancee]:
    _verifier_admin(current_user)
    contenu = await fichier.read(30 * 1024 * 1024 + 1)
    try:
        task_id = svc.lancer_import_fichier(contenu, annee, mois)
    except svc.BaseClientsErreur as exc:
        raise _erreur(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ApiResponse.success(TacheLancee(task_id=task_id, message=f"Import de {mois:02d}/{annee} lancé"))


# ── Atelier : lien poste ↔ unité de relève ───────────────────────────────────
# Routes statiques avant les routes à paramètre.


@router.get("/atelier/droits", response_model=ApiResponse[DroitsAtelier], summary="Droits du compte sur l'atelier")
async def droits_atelier(
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[DroitsAtelier]:
    return ApiResponse.success(await atelier.get_droits(db, current_user))


@router.get("/atelier/postes", response_model=ApiResponse[list[PosteRecherche]], summary="Rechercher un poste")
async def rechercher_postes(
    recherche: str = Query(..., min_length=2, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[list[PosteRecherche]]:
    return ApiResponse.success(await atelier.rechercher_postes(db, current_user, recherche))


@router.get(
    "/atelier/unites-releve",
    response_model=ApiResponse[list[UniteReleveRecherche]],
    summary="Rechercher une unité de relève (dernier mois chargé)",
)
async def rechercher_ur(
    recherche: str = Query(..., min_length=3, max_length=20),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[list[UniteReleveRecherche]]:
    return ApiResponse.success(await atelier.rechercher_ur(db, current_user, recherche))


@router.get("/atelier/liens", response_model=ApiResponse[PaginatedResponse[LienPosteUR]], summary="Liens poste ↔ UR")
async def lister_liens(
    poste_id: int | None = Query(None, ge=1),
    a_valider: bool = Query(False, description="Uniquement les propositions en attente"),
    recherche: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[PaginatedResponse[LienPosteUR]]:
    return ApiResponse.success(
        await atelier.lister(
            db,
            current_user,
            poste_id=poste_id,
            a_valider=a_valider,
            recherche=recherche,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/atelier/liens",
    response_model=ApiResponse[ActionAtelier],
    status_code=status.HTTP_201_CREATED,
    summary="Proposer le rattachement d'une UR à un poste",
)
async def proposer_ajout(
    data: LienPosteURCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[ActionAtelier]:
    lien_id = await atelier.proposer_ajout(db, current_user, data)
    return ApiResponse.success(ActionAtelier(id=lien_id, message="Ajout proposé, en attente de validation"))


@router.delete("/atelier/liens/{lien_id}", response_model=ApiResponse[ActionAtelier], summary="Proposer le retrait")
async def proposer_retrait(
    lien_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[ActionAtelier]:
    message = await atelier.proposer_retrait(db, current_user, lien_id)
    return ApiResponse.success(ActionAtelier(id=lien_id, message=message))


@router.post("/atelier/liens/{lien_id}/valider", response_model=ApiResponse[ActionAtelier], summary="Valider")
async def valider_lien(
    lien_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[ActionAtelier]:
    message, postes = await atelier.decider(db, current_user, lien_id, accepter=True)
    atelier.lancer_recalcul(postes)
    return ApiResponse.success(ActionAtelier(id=lien_id, message=message))


@router.post("/atelier/liens/{lien_id}/rejeter", response_model=ApiResponse[ActionAtelier], summary="Rejeter")
async def rejeter_lien(
    lien_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[ActionAtelier]:
    message, _ = await atelier.decider(db, current_user, lien_id, accepter=False)
    return ApiResponse.success(ActionAtelier(id=lien_id, message=message))
