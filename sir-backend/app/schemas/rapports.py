"""Schémas Pydantic — rapports CRSE (Sprint 6)."""

from datetime import date as DateType
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RapportJournalierRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    report_date: DateType | None = Field(
        None,
        alias="date",
        description="Date du rapport (défaut : jour courant)",
    )
    region_id: int | None = Field(None, ge=1)
    output_format: Literal["pdf", "xlsx"] = Field("pdf", alias="format")


class RapportHebdomadaireRequest(BaseModel):
    """Semaine du lundi contenant `date_debut` (défaut : semaine précédente)."""

    model_config = ConfigDict(populate_by_name=True)

    date_debut: DateType | None = None
    region_id: int | None = Field(None, ge=1)
    output_format: Literal["pdf", "xlsx"] = Field("pdf", alias="format")


class RapportEnqueueResponse(BaseModel):
    task_id: str
    type_rapport: str
    statut: str
    format: str


class RapportStatusResponse(BaseModel):
    task_id: str
    type_rapport: str
    format: str
    statut: str
    error_message: str | None = None
    file_name: str | None = None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
