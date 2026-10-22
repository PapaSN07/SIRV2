"""Service métier — Assistant SIR (lecture + conseil, phase P0)."""

from __future__ import annotations

import json
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac_helpers import has_any_role, is_superadmin
from app.models.assistant_ml import MlPrediction
from app.models.utilisateurs import Utilisateur
from app.repositories import assistant_ml_repository as repo
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantFeedbackResponse,
    DatamartFeederMoisItem,
    DatamartPosteItem,
    DatamartSummaryResponse,
    DatamartTronconItem,
    RiskFactor,
    RiskListResponse,
    RiskPredictionResponse,
    ScoringJobResponse,
)
from app.services import ml_scoring_service


def _parse_factors(raw: str | None) -> list[RiskFactor]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    factors: list[RiskFactor] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        factors.append(
            RiskFactor(
                code=str(item.get("code") or "factor"),
                label=str(item.get("label") or ""),
                weight=float(item["weight"]) if item.get("weight") is not None else None,
            )
        )
    return factors


def _prediction_to_response(row: MlPrediction) -> RiskPredictionResponse:
    return RiskPredictionResponse(
        id=row.id,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        entity_libelle=row.entity_libelle,
        horizon_days=row.horizon_days,
        risk_score=float(row.risk_score),
        risk_level=row.risk_level,
        model_version=row.model_version,
        factors=_parse_factors(row.factors_json),
        recommendation=row.recommendation,
        service_id=row.service_id,
        feeder_id=row.feeder_id,
        calculated_at=row.calculated_at,
    )


def _user_role_names(user: Utilisateur) -> set[str]:
    return {ur.role.nom for ur in user.user_roles}


async def _user_service_scope(
    db: AsyncSession, user: Utilisateur
) -> list[int] | None:
    """None = national ; liste = filtre service_id obligatoire."""
    roles = _user_role_names(user)
    if is_superadmin(user) or roles.intersection({"ADMIN_SCR", "ADMIN_SAQS"}):
        return None
    if roles.intersection({"ADMIN_DISPATCHING", "DISPATCHER"}) and not roles.intersection(
        {"ADMIN_SCR", "ADMIN_SAQS", "SUPERADMIN", "BCC", "BRC", "SUPERVISEUR"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Assistant distribution non accessible au périmètre transport seul",
            },
        )
    if roles.intersection({"BRC"}):
        region_id = user.user_roles[0].scope_service_id
        if region_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Périmètre régional non configuré pour l'Assistant",
                },
            )
        from app.repositories import indicateurs_repository as ind_repo

        service_ids = await ind_repo.list_service_ids_for_region(db, region_id)
        if not service_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "error",
                    "data": None,
                    "error": "Aucun service pour la région du compte",
                },
            )
        return service_ids

    service_ids = [
        ur.scope_service_id
        for ur in user.user_roles
        if ur.scope_service_id is not None
    ]
    if not service_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Périmètre service non défini pour l'Assistant",
            },
        )
    return service_ids


async def get_risks(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    feeder_id: int | None = None,
    risk_level: str | None = None,
    limit: int = 30,
) -> RiskListResponse:
    service_ids = await _user_service_scope(db, current_user)
    rows = await repo.list_active_predictions(
        db,
        entity_type="feeder",
        feeder_id=feeder_id,
        service_ids=service_ids,
        risk_level=risk_level,
        limit=limit,
    )
    items = [_prediction_to_response(r) for r in rows]
    horizon = items[0].horizon_days if items else ml_scoring_service.DEFAULT_HORIZON_DAYS
    version = items[0].model_version if items else ml_scoring_service.MODEL_VERSION
    return RiskListResponse(items=items, model_version=version, horizon_days=horizon)


async def get_feeder_risk(
    db: AsyncSession,
    current_user: Utilisateur,
    feeder_id: int,
) -> RiskPredictionResponse:
    service_ids = await _user_service_scope(db, current_user)
    row = await repo.get_latest_feeder_prediction(
        db, feeder_id, service_ids=service_ids
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": f"Aucune prédiction active pour le feeder {feeder_id}",
            },
        )
    return _prediction_to_response(row)


async def get_datamart(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    feeder_id: int | None = None,
) -> DatamartSummaryResponse:
    service_ids = await _user_service_scope(db, current_user)
    feeders = await repo.list_datamart_feeder_mois(db, service_ids=service_ids, limit=60)
    troncons = await repo.list_datamart_troncon_sig(db, service_ids=service_ids, limit=40)
    postes = await repo.list_datamart_poste(
        db, service_ids=service_ids, feeder_id=feeder_id, limit=40
    )
    return DatamartSummaryResponse(
        feeders_mois=[DatamartFeederMoisItem(**row) for row in feeders],
        troncons_sig=[DatamartTronconItem(**row) for row in troncons],
        postes=[DatamartPosteItem(**row) for row in postes],
    )


def _build_chat_answer(
    question: str,
    predictions: list[RiskPredictionResponse],
    *,
    feeder_id: int | None,
) -> str:
    q = question.lower().strip()
    top = predictions[:5]

    if re.search(r"travaux|maintenance|préventif|preventif", q):
        high = [p for p in predictions if p.risk_level in {"high", "critical"}]
        if not high:
            return (
                "Aucun départ en risque élevé actuellement. "
                "Vous pouvez planifier les travaux selon le planning habituel."
            )
        lines = [
            "Départs à prioriser pour travaux préventifs (conseil P0) :",
            *[
                f"- {p.entity_libelle or p.entity_id} : score {p.risk_score:.0f} ({p.risk_level}) — {p.recommendation}"
                for p in high[:5]
            ],
        ]
        return "\n".join(lines)

    if feeder_id is not None or re.search(r"feeder|départ|depart", q):
        if not predictions:
            return (
                "Pas encore de score pour ce feeder. "
                "Lancez le scoring (job Celery) ou vérifiez le périmètre."
            )
        p = predictions[0]
        factors = "; ".join(f.label for f in p.factors[:4]) or "n/d"
        return (
            f"Risque sur {p.entity_libelle or p.entity_id} : "
            f"{p.risk_score:.0f}/100 ({p.risk_level}). "
            f"Facteurs : {factors}. "
            f"Recommandation : {p.recommendation or 'suivre le départ'}."
        )

    if not top:
        return (
            "Aucune alerte active. L'Assistant s'appuie sur les scores P0 "
            "(fréquence, natures permanentes, durée, clients)."
        )
    lines = [
        "Top risques feeders (fenêtre courante) :",
        *[
            f"- {p.entity_libelle or p.entity_id} : {p.risk_score:.0f} ({p.risk_level})"
            for p in top
        ],
        "Posez une question du type « quels travaux prioriser ? » ou filtrez par feeder.",
    ]
    return "\n".join(lines)


async def chat(
    db: AsyncSession,
    current_user: Utilisateur,
    body: AssistantChatRequest,
) -> AssistantChatResponse:
    service_ids = await _user_service_scope(db, current_user)
    rows = await repo.list_active_predictions(
        db,
        entity_type="feeder",
        feeder_id=body.feeder_id,
        service_ids=service_ids,
        limit=30,
    )
    predictions = [_prediction_to_response(r) for r in rows]
    answer = _build_chat_answer(
        body.question, predictions, feeder_id=body.feeder_id
    )
    context: dict[str, Any] = {
        "phase": "P0",
        "feeder_id": body.feeder_id,
        "interruption_id": body.interruption_id,
        "nb_predictions": len(predictions),
    }
    conversation = await repo.add_conversation(
        db,
        user=current_user,
        question=body.question,
        answer=answer[:4000],
        context_json=json.dumps(context, ensure_ascii=False)[:2000],
        feeder_id=body.feeder_id,
        interruption_id=body.interruption_id,
    )
    await db.commit()
    return AssistantChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        predictions=predictions[:10],
        phase="P0",
    )


async def feedback(
    db: AsyncSession,
    current_user: Utilisateur,
    conversation_id: int,
    accepted: bool,
) -> AssistantFeedbackResponse:
    row = await repo.set_conversation_feedback(
        db, conversation_id, current_user.id, accepted
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "data": None,
                "error": "Conversation introuvable",
            },
        )
    await db.commit()
    return AssistantFeedbackResponse(
        conversation_id=row.id, accepted=bool(row.accepted)
    )


async def run_scoring(
    db: AsyncSession,
    current_user: Utilisateur,
    *,
    horizon_days: int = ml_scoring_service.DEFAULT_HORIZON_DAYS,
) -> ScoringJobResponse:
    """Scoring synchrone (admin) — le job Celery reste le chemin nominal."""
    if not has_any_role(
        current_user, {"ADMIN_SCR", "ADMIN_SAQS", "SUPERADMIN"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "data": None,
                "error": "Recalcul scoring réservé ADMIN_SCR / ADMIN_SAQS",
            },
        )
    service_ids = await _user_service_scope(db, current_user)
    result = await ml_scoring_service.score_feeders(
        db, horizon_days=horizon_days, service_ids=service_ids
    )
    return ScoringJobResponse(
        status=str(result["status"]),
        feeders_scored=int(result["feeders_scored"]),
        model_version=str(result["model_version"]),
        horizon_days=int(result["horizon_days"]),
    )
