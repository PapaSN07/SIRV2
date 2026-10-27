"""Schémas — cycle de vie d'une interruption (historique, renvoi, dévalidation, archivage)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class MotifRequest(BaseModel):
    """Renvoi en correction ou dévalidation : le motif est obligatoire et affiché au saisisseur."""

    motif: str = Field(..., min_length=5, max_length=1000)

    @field_validator("motif")
    @classmethod
    def _motif_non_vide(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Motif obligatoire (5 caractères minimum)")
        return value


class StatutHistoriqueResponse(BaseModel):
    id: int
    action: str
    ancien_statut: str | None
    nouveau_statut: str
    motif: str | None
    utilisateur_id: int
    utilisateur_nom: str | None = None
    created_at: datetime


class ArchivageRequest(BaseModel):
    annee: int = Field(..., ge=2000, le=2100)
    mois: int = Field(..., ge=1, le=12)


class ArchivageResponse(BaseModel):
    annee: int
    mois: int
    archivees: int
    non_validees_restantes: int


class ValidationLotRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, max_length=200)


class ValidationLotEchec(BaseModel):
    id: int
    erreur: str


class ValidationLotResponse(BaseModel):
    validees: list[int]
    echecs: list[ValidationLotEchec]
