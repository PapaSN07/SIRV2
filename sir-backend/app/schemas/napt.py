from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

NaptStatut = Literal["brouillon", "soumis", "approuve", "rejete", "archive"]
ConsignationStatut = Literal["ouverte", "levee", "annulee"]


class NaptCreate(BaseModel):
    service_id: int = Field(..., ge=1)
    feeder_id: int | None = Field(default=None, ge=1)
    objet_travaux: str = Field(..., min_length=1, max_length=1000)
    date_debut_prevue: datetime
    date_fin_prevue: datetime
    is_interruption_necessaire: bool = False
    observations: str | None = Field(default=None, max_length=2000)


class NaptUpdate(BaseModel):
    feeder_id: int | None = Field(default=None, ge=1)
    objet_travaux: str | None = Field(default=None, min_length=1, max_length=1000)
    date_debut_prevue: datetime | None = None
    date_fin_prevue: datetime | None = None
    is_interruption_necessaire: bool | None = None
    observations: str | None = Field(default=None, max_length=2000)


class ConsignationCreate(BaseModel):
    numero_consignation: str = Field(..., min_length=1, max_length=50)
    date_ouverture: datetime
    agent_consignateur_id: int = Field(..., ge=1)
    observations: str | None = Field(default=None, max_length=2000)


class ConsignationResponse(BaseModel):
    id: int
    napt_id: int
    numero_consignation: str
    statut: ConsignationStatut
    date_ouverture: datetime
    date_levee: datetime | None
    agent_consignateur_id: int
    observations: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NaptResponse(BaseModel):
    id: int
    numero_napt: str
    service_id: int
    feeder_id: int | None
    statut: NaptStatut
    objet_travaux: str
    date_debut_prevue: datetime
    date_fin_prevue: datetime
    date_debut_reelle: datetime | None
    date_fin_reelle: datetime | None
    is_interruption_necessaire: bool
    observations: str | None
    created_by_id: int
    approved_by_id: int | None
    created_at: datetime
    updated_at: datetime
    service_libelle: str | None = None
    feeder_libelle: str | None = None
    consignations: list[ConsignationResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
