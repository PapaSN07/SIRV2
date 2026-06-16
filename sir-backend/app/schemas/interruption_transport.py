"""Schémas Pydantic — interruptions réseau transport (Sprint 4)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.interruption_distribution import (
    EnergieNdSummaryResponse,
    InterruptionClotureRequest,
    UtilisateurSummaryResponse,
)

TypeDirectionTransport = Literal["transport", "omvg"]
StatutInterruption = Literal["en_cours", "cloture", "valide", "archive"]

CREATE_ROLES = frozenset({"DISPATCHER", "ADMIN_DISPATCHING"})
READ_ROLES = frozenset({"DISPATCHER", "ADMIN_DISPATCHING", "ADMIN_SAQS"})
VALIDATE_ROLES = frozenset({"ADMIN_DISPATCHING", "ADMIN_SAQS"})


class InterruptionTransportFilters(BaseModel):
    type_direction: TypeDirectionTransport | None = None
    statut: StatutInterruption | None = None
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    equipement_transport_id: int | None = Field(default=None, ge=1)
    source_transport_id: int | None = Field(default=None, ge=1)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class InterruptionTransportCreate(BaseModel):
    type_direction: TypeDirectionTransport = "transport"
    date_apparition: datetime
    equipement_transport_id: int = Field(..., ge=1)
    source_transport_id: int | None = Field(default=None, ge=1)
    poste_ligne_id: int | None = Field(default=None, ge=1)
    cause_id: int = Field(..., ge=1)
    nature_id: int = Field(..., ge=1)
    siege_id: int = Field(..., ge=1)
    signalisation_id: int = Field(..., ge=1)
    tension_kv: float | None = Field(default=None, ge=0)
    puissance_transit_mw: float | None = Field(default=None, ge=0)
    puissance_coupee_mw: float | None = Field(default=None, ge=0)
    localisation: str | None = Field(default=None, max_length=500)
    observations: str | None = Field(default=None, max_length=2000)
    is_force_majeure: bool = False
    is_fugitive: bool = False


class InterruptionTransportUpdate(BaseModel):
    date_apparition: datetime | None = None
    cause_id: int | None = Field(default=None, ge=1)
    nature_id: int | None = Field(default=None, ge=1)
    siege_id: int | None = Field(default=None, ge=1)
    signalisation_id: int | None = Field(default=None, ge=1)
    puissance_coupee_mw: float | None = Field(default=None, ge=0)
    localisation: str | None = Field(default=None, max_length=500)
    observations: str | None = Field(default=None, max_length=2000)
    is_force_majeure: bool | None = None
    is_fugitive: bool | None = None
    tension_kv: float | None = Field(default=None, ge=0)
    puissance_transit_mw: float | None = Field(default=None, ge=0)
    source_transport_id: int | None = Field(default=None, ge=1)


class InterruptionTransportResponse(BaseModel):
    id: int
    numero_interruption: int
    type_direction: TypeDirectionTransport
    statut: StatutInterruption
    service_id: int | None
    date_apparition: datetime
    date_remise: datetime | None
    duree_minutes: int | None
    cause_id: int | None
    nature_id: int | None
    siege_id: int | None
    signalisation_id: int | None
    puissance_coupee_mw: float | None
    localisation: str | None
    observations: str | None
    is_force_majeure: bool
    is_fugitive: bool
    tension_kv: float | None = None
    equipement_transport_id: int | None = None
    source_transport_id: int | None = None
    puissance_transit_mw: float | None = None
    energie_non_fournie_mwh: float | None = None
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InterruptionTransportDetailResponse(InterruptionTransportResponse):
    equipement_libelle: str | None = None
    source_libelle: str | None = None
    cause_libelle: str | None = None
    nature_libelle: str | None = None
    siege_libelle: str | None = None
    signalisation_libelle: str | None = None
    energie_nd: EnergieNdSummaryResponse | None = None
    created_by: UtilisateurSummaryResponse | None = None
    validated_by: UtilisateurSummaryResponse | None = None
    validated_by_id: int | None = None
