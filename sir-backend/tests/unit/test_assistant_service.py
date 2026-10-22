"""Tests unitaires — réponses chat Assistant (P0 sans LLM)."""

from app.schemas.assistant import RiskFactor, RiskPredictionResponse
from app.services.assistant_service import _build_chat_answer
from datetime import datetime


def _pred(score: float, level: str, libelle: str = "FEEDER A") -> RiskPredictionResponse:
    return RiskPredictionResponse(
        id=1,
        entity_type="feeder",
        entity_id=10,
        entity_libelle=libelle,
        horizon_days=90,
        risk_score=score,
        risk_level=level,
        model_version="p0-rules-v1",
        factors=[RiskFactor(code="frequence", label="10 interruptions", weight=20)],
        recommendation="Surveiller",
        service_id=1,
        feeder_id=10,
        calculated_at=datetime(2026, 9, 1, 12, 0, 0),
    )


def test_chat_travaux_lists_high_risk() -> None:
    preds = [_pred(80, "critical"), _pred(20, "low", "FEEDER B")]
    answer = _build_chat_answer("Quels travaux prioriser ?", preds, feeder_id=None)
    assert "FEEDER A" in answer
    assert "FEEDER B" not in answer


def test_chat_feeder_explains_score() -> None:
    preds = [_pred(42, "medium")]
    answer = _build_chat_answer("risque du feeder ?", preds, feeder_id=10)
    assert "42" in answer
    assert "medium" in answer
