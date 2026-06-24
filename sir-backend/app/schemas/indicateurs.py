"""Schémas Pydantic — indicateurs CRSE (Sprint 5)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class SaifiSaidiCalculationResult(BaseModel):
    interruption_id: int
    service_id: int | None = None
    annee: int | None = None
    mois: int | None = None
    status: str
    saifi: float | None = None
    saidi: float | None = None
    nombre_interruptions: int | None = None
    total_clients_reference: int | None = None
    region_id: int | None = None


class SaifiSaidiRecordResponse(BaseModel):
    service_id: int
    annee: int
    mois: int
    saifi: float
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int
    calculated_at: datetime

    model_config = {"from_attributes": True}


class SaifiSaidiAggregateResponse(BaseModel):
    niveau: str = Field(..., description="service | delegation | region | national")
    scope_id: int | None = None
    annee: int
    mois: int
    saifi: float
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int


class EndServiceItemResponse(BaseModel):
    service_id: int
    end_mwh: float
    nombre_interruptions: int


class EndAggregateResponse(BaseModel):
    niveau: str = Field(..., description="service | delegation | region | national")
    scope_id: int | None = None
    annee: int
    mois: int
    end_mwh: float
    nombre_interruptions: int


class SaifiServiceItemResponse(BaseModel):
    service_id: int
    saifi: float
    nombre_interruptions: int
    total_clients_reference: int


class SaidiServiceItemResponse(BaseModel):
    service_id: int
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int


class EndIndicateurResponse(BaseModel):
    aggregate: EndAggregateResponse
    services: PaginatedResponse[EndServiceItemResponse] | None = None


class SaifiIndicateurResponse(BaseModel):
    aggregate: SaifiSaidiAggregateResponse
    services: PaginatedResponse[SaifiServiceItemResponse] | None = None


class SaidiIndicateurResponse(BaseModel):
    aggregate: SaifiSaidiAggregateResponse
    services: PaginatedResponse[SaidiServiceItemResponse] | None = None


class TableauDeBordResponse(BaseModel):
    niveau: str
    scope_id: int | None = None
    annee: int
    mois: int
    end_mois: float
    saifi: float
    saidi: float
    nb_interruptions_actives: int
    nb_interruptions_mois: int
    causes_repartition: list["CauseRepartitionItemResponse"] = Field(default_factory=list)


class CauseRepartitionItemResponse(BaseModel):
    label: str
    nombre: int
    percent: float


class HistoriquePointResponse(BaseModel):
    annee: int
    mois: int
    valeur: float


class HistoriqueResponse(BaseModel):
    type: str = Field(..., description="end | saifi | saidi")
    niveau: str
    scope_id: int | None = None
    annees: int
    points: list[HistoriquePointResponse]


class TopFeederItemResponse(BaseModel):
    feeder_id: int
    code: str
    libelle: str
    service_id: int | None = None
    end_mwh: float
    nombre_interruptions: int


class TopFeedersResponse(BaseModel):
    niveau: str
    scope_id: int | None = None
    annee: int
    mois: int
    limit: int
    items: list[TopFeederItemResponse]
