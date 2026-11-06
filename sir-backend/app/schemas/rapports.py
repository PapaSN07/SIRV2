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


class RapportHebdoDDRequest(BaseModel):
    """Rapport hebdomadaire d'exploitation DD : semaine samedi → vendredi se terminant par
    le vendredi `date_fin` (défaut : dernière semaine complète). Les trois fichiers (Word,
    Excel, PDF) sont produits ; `format` choisit celui qui est téléchargé."""

    model_config = ConfigDict(populate_by_name=True)

    date_fin: DateType | None = None
    output_format: Literal["docx", "xlsx", "pdf"] = Field("docx", alias="format")


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


# --------------------------------------------------------------------------------------
# Aperçus graphiques (page Rapports) : les chiffres du rapport, sans générer le fichier
# --------------------------------------------------------------------------------------


class ApercuValeur(BaseModel):
    libelle: str
    valeur: float
    precedent: float | None = None


class ApercuSerie(BaseModel):
    """Une ligne d'un graphique en barres : libellé, valeur (et valeur de comparaison)."""

    libelle: str
    nombre: int = 0
    end_mwh: float = 0.0
    nombre_precedent: int | None = None
    end_mwh_precedent: float | None = None
    part_pct: float | None = None


class ApercuHebdoDDResponse(BaseModel):
    debut: DateType
    fin: DateType
    numero: int
    numero_precedent: int
    indicateurs: list[ApercuValeur]
    categories: list[ApercuSerie]
    services: list[ApercuSerie]
    jours: list[ApercuSerie]


class ApercuMensuelDistributionResponse(BaseModel):
    annee: int
    mois: int
    region_id: int | None = None
    indicateurs: list[ApercuValeur]
    services: list[ApercuSerie]
    top_feeders: list[ApercuSerie]
