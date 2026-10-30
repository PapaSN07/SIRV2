"""Base clients SAIFI/SAIDI : contrats par unité de relève (BI_ODS ou fichier H2MC mensuel)."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.base_clients import BaseClientsResume, TacheLancee
from app.schemas.common import ApiResponse
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
