"""API Assistant ML — risque panne / travaux (lecture seule + chat conseil)."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.utilisateurs import Utilisateur
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantFeedbackRequest,
    AssistantFeedbackResponse,
    DatamartSummaryResponse,
    RiskListResponse,
    RiskPredictionResponse,
    ScoringJobResponse,
)
from app.schemas.common import ApiResponse
from app.services import assistant_service

router = APIRouter()


@router.get(
    "/risk",
    response_model=ApiResponse[RiskListResponse],
    summary="Liste des scores de risque actifs (feeders)",
)
async def list_risks(
    feeder_id: int | None = Query(default=None, ge=1),
    risk_level: str | None = Query(default=None),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "read")),
) -> ApiResponse[RiskListResponse]:
    result = await assistant_service.get_risks(
        db,
        current_user,
        feeder_id=feeder_id,
        risk_level=risk_level,
        limit=limit,
    )
    return ApiResponse.success(result)


@router.get(
    "/risk/feeder/{feeder_id}",
    response_model=ApiResponse[RiskPredictionResponse],
    summary="Score de risque pour un feeder",
)
async def get_feeder_risk(
    feeder_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "read")),
) -> ApiResponse[RiskPredictionResponse]:
    result = await assistant_service.get_feeder_risk(db, current_user, feeder_id)
    return ApiResponse.success(result)


@router.get(
    "/datamart",
    response_model=ApiResponse[DatamartSummaryResponse],
    summary="Datamart lecture seule (feeders / tronçons SIG / postes)",
)
async def get_datamart(
    feeder_id: int | None = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "read")),
) -> ApiResponse[DatamartSummaryResponse]:
    result = await assistant_service.get_datamart(
        db, current_user, feeder_id=feeder_id
    )
    return ApiResponse.success(result)


@router.post(
    "/chat",
    response_model=ApiResponse[AssistantChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Question à l'Assistant (conseil P0, sans LLM obligatoire)",
)
async def chat(
    body: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "read")),
) -> ApiResponse[AssistantChatResponse]:
    result = await assistant_service.chat(db, current_user, body)
    return ApiResponse.success(result)


@router.post(
    "/chat/{conversation_id}/feedback",
    response_model=ApiResponse[AssistantFeedbackResponse],
    summary="Feedback accepté / rejeté sur une suggestion",
)
async def chat_feedback(
    conversation_id: int,
    body: AssistantFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "read")),
) -> ApiResponse[AssistantFeedbackResponse]:
    result = await assistant_service.feedback(
        db, current_user, conversation_id, body.accepted
    )
    return ApiResponse.success(result)


@router.post(
    "/scoring/run",
    response_model=ApiResponse[ScoringJobResponse],
    summary="Recalcul synchrone des scores P0 (admins)",
)
async def run_scoring(
    horizon_days: int = Query(90, ge=30, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: Utilisateur = Depends(require_permission("assistant", "admin")),
) -> ApiResponse[ScoringJobResponse]:
    result = await assistant_service.run_scoring(
        db, current_user, horizon_days=horizon_days
    )
    return ApiResponse.success(result)


@router.post(
    "/scoring/enqueue",
    response_model=ApiResponse[dict],
    summary="Enfile le job Celery de scoring hebdomadaire",
)
async def enqueue_scoring(
    horizon_days: int = Query(90, ge=30, le=365),
    current_user: Utilisateur = Depends(require_permission("assistant", "admin")),
) -> ApiResponse[dict]:
    from app.workers.tasks.assistant_ml import score_feeder_risk_task

    async_result = score_feeder_risk_task.delay(horizon_days)
    return ApiResponse.success(
        {
            "task_id": async_result.id,
            "status": "queued",
            "horizon_days": horizon_days,
            "requested_by": current_user.id,
        }
    )
