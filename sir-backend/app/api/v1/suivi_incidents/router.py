"""Menu « Suivi incidents » (fusion du tableau de bord Suivi incidents SIR dans SIRV2).

RBAC en double : ``require_permission("indicateurs", "read")`` ici, et clause SQL de la région
(BCC / BRC) ou du service (SUPERVISEUR) imposés par ``resoudre_filtres`` dans le service.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.redis import get_redis
from app.models.utilisateurs import Utilisateur
from app.schemas.common import ApiResponse
from app.schemas.suivi_incidents import ClassementSuivi, FiltresResolus, VueEnsemble
from app.services import suivi_incidents_service

router = APIRouter()


def filtres_requete(
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
) -> dict[str, Any]:
    """Filtres bruts communs aux onglets, validés par ``resoudre_filtres`` (422 enveloppé)."""
    return {
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
    }


@router.get(
    "/filtres",
    response_model=ApiResponse[FiltresResolus],
    status_code=status.HTTP_200_OK,
    summary="Filtres du suivi des incidents complétés (période par défaut, périmètre du rôle)",
)
async def get_filtres(
    bruts: dict[str, Any] = Depends(filtres_requete),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[FiltresResolus]:
    return ApiResponse.success(suivi_incidents_service.resoudre_filtres(current_user, bruts))


@router.get(
    "/vue-ensemble",
    response_model=ApiResponse[VueEnsemble],
    status_code=status.HTTP_200_OK,
    summary="Vue d'ensemble : KPI (et période précédente), natures, réseaux HTA / HTB",
)
async def get_vue_ensemble(
    bruts: dict[str, Any] = Depends(filtres_requete),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[VueEnsemble]:
    return ApiResponse.success(await suivi_incidents_service.vue_ensemble(db, redis, current_user, bruts))


@router.get(
    "/classement",
    response_model=ApiResponse[ClassementSuivi],
    status_code=status.HTTP_200_OK,
    summary="Services, postes sources ou feeders les plus touchés",
)
async def get_classement(
    bruts: dict[str, Any] = Depends(filtres_requete),
    niveau: str | None = Query(None, description="service | poste_source | feeder (obligatoire)"),
    limite: str | None = Query(None, description="Nombre de lignes, 1 à 50 (défaut 10)"),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: Utilisateur = Depends(require_permission("indicateurs", "read")),
) -> ApiResponse[ClassementSuivi]:
    resultat = await suivi_incidents_service.classement(db, redis, current_user, bruts, niveau, limite)
    return ApiResponse.success(resultat)
