"""Menu « Suivi incidents » (fusion du tableau de bord Suivi incidents SIR dans SIRV2)."""

from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.suivi_incidents import FiltresResolus
from app.services import suivi_incidents_service

router = APIRouter()


@router.get(
    "/filtres",
    response_model=ApiResponse[FiltresResolus],
    status_code=status.HTTP_200_OK,
    summary="Filtres du suivi des incidents complétés (période par défaut, périmètre du rôle)",
)
async def get_filtres(
    debut: date | None = Query(None, description="Premier jour (défaut : samedi de la dernière semaine SENELEC)"),
    fin: date | None = Query(None, description="Dernier jour inclus"),
    region_id: int | None = Query(None),
    service_id: int | None = Query(None),
    poste_source_id: int | None = Query(None),
    feeder_id: int | None = Query(None),
    nature_id: int | None = Query(None),
    cause_id: int | None = Query(None),
    reseau: str | None = Query(None, description="hta | htb"),
    exogene: bool | None = Query(None),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[FiltresResolus]:
    resultat = suivi_incidents_service.resoudre_filtres(
        current_user,
        {
            "debut": debut,
            "fin": fin,
            "region_id": region_id,
            "service_id": service_id,
            "poste_source_id": poste_source_id,
            "feeder_id": feeder_id,
            "nature_id": nature_id,
            "cause_id": cause_id,
            "reseau": reseau,
            "exogene": exogene,
        },
    )
    return ApiResponse.success(resultat)
