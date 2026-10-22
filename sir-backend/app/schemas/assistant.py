"""Schémas API — Assistant ML (risque panne / travaux, chat, datamart)."""

from datetime import datetime

from pydantic import BaseModel, Field


class RiskFactor(BaseModel):
    code: str
    label: str
    weight: float | None = None


class RiskPredictionResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    entity_libelle: str | None = None
    horizon_days: int
    risk_score: float
    risk_level: str
    model_version: str
    factors: list[RiskFactor] = Field(default_factory=list)
    recommendation: str | None = None
    service_id: int | None = None
    feeder_id: int | None = None
    calculated_at: datetime


class RiskListResponse(BaseModel):
    items: list[RiskPredictionResponse]
    model_version: str
    horizon_days: int
    generated_hint: str = (
        "Scores P0 (règles/stats) — conseil uniquement, ne bloque pas la saisie."
    )


class DatamartFeederMoisItem(BaseModel):
    feeder_id: int
    feeder_code: str | None = None
    feeder_libelle: str | None = None
    service_id: int | None = None
    annee: int
    mois: int
    nb_interruptions: int
    nb_force_majeure: int
    duree_moyenne_minutes: float | None = None
    clients_touches_total: int


class DatamartTronconItem(BaseModel):
    troncon_sig_id: int
    troncon_sig_libelle: str | None = None
    feeder_id: int | None = None
    service_id: int | None = None
    nb_interruptions: int
    duree_moyenne_minutes: float | None = None
    derniere_apparition: datetime | None = None


class DatamartPosteItem(BaseModel):
    poste_id: int
    poste_code: str | None = None
    poste_libelle: str | None = None
    feeder_id: int | None = None
    service_id: int | None = None
    nb_impactes: int
    clients_touches_total: int
    derniere_apparition: datetime | None = None


class DatamartSummaryResponse(BaseModel):
    feeders_mois: list[DatamartFeederMoisItem]
    troncons_sig: list[DatamartTronconItem]
    postes: list[DatamartPosteItem]


class AssistantChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    feeder_id: int | None = Field(default=None, ge=1)
    interruption_id: int | None = Field(default=None, ge=1)


class AssistantChatResponse(BaseModel):
    conversation_id: int
    answer: str
    predictions: list[RiskPredictionResponse] = Field(default_factory=list)
    phase: str = "P0"
    disclaimer: str = (
        "Assistant conseil — validation humaine obligatoire pour travaux / clôture."
    )


class AssistantFeedbackRequest(BaseModel):
    accepted: bool


class AssistantFeedbackResponse(BaseModel):
    conversation_id: int
    accepted: bool


class ScoringJobResponse(BaseModel):
    status: str
    feeders_scored: int
    model_version: str
    horizon_days: int
