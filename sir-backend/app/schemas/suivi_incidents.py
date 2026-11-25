"""Schémas du menu « Suivi incidents » : filtres communs aux onglets."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Plage maximale d'une période (fin incluse) : trois ans
DUREE_MAX_JOURS = 1096


class FiltresIncidents(BaseModel):
    """Filtres d'une vue du suivi des incidents (interruptions distribution)."""

    debut: date
    fin: date = Field(..., description="Dernier jour inclus")
    region_id: int | None = Field(None, ge=1)
    service_id: int | None = Field(None, ge=1)
    poste_source_id: int | None = Field(None, ge=1)
    feeder_id: int | None = Field(None, ge=1)
    nature_id: int | None = Field(None, ge=1)
    cause_id: int | None = Field(None, ge=1)
    reseau: Literal["hta", "htb"] | None = Field(
        None, description="Réseau en cause : HTB = cause HTB / PRODUCTION / BLACK START (décision du 25/11/2026)"
    )
    exogene: bool | None = Field(None, description="Cause marquée facteur exogène")

    @model_validator(mode="after")
    def _periode_valide(self) -> "FiltresIncidents":
        if self.fin < self.debut:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début")
        if (self.fin - self.debut).days + 1 > DUREE_MAX_JOURS:
            raise ValueError("La période ne peut pas dépasser trois ans")
        return self


class SemaineSenelecSchema(BaseModel):
    numero: int
    annee: int
    debut: date
    fin: date


class PerimetreSuivi(BaseModel):
    niveau: Literal["national", "region", "service"]
    scope_id: int | None = None
    region_verrouillee: bool = False
    service_verrouille: bool = False


class FiltresResolus(BaseModel):
    """Filtres complétés : période par défaut, périmètre imposé par le rôle, libellé."""

    filtres: FiltresIncidents
    semaine: SemaineSenelecSchema | None = Field(
        None, description="Renseignée quand la période est exactement une semaine SENELEC"
    )
    libelle_periode: str
    perimetre: PerimetreSuivi
