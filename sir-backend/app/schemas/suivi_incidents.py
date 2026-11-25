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


# ── Onglet Vue d'ensemble ─────────────────────────────────────────────────────────────────

CategorieNature = Literal["incident", "delestage", "travaux", "autre"]
NiveauClassement = Literal["service", "poste_source", "feeder"]


class PeriodeSuivi(BaseModel):
    debut: date
    fin: date
    libelle: str


class KpiSuivi(BaseModel):
    nombre_interruptions: int
    duree_totale_heures: float
    duree_moyenne_minutes: float | None = Field(None, description="Moyenne des durées renseignées")
    postes_touches: int
    coupures_clients: int = Field(..., description="Σ clients touchés par interruption")
    end_mwh: float


class RepartitionNature(BaseModel):
    categorie: CategorieNature
    libelle: str
    nombre: int
    duree_heures: float
    end_mwh: float
    part: float = Field(..., description="Part du nombre d'interruptions (0 à 1)")


class RepartitionReseau(BaseModel):
    reseau: Literal["hta", "htb", "total"]
    nombre: int
    duree_heures: float
    end_mwh: float


class VueEnsemble(BaseModel):
    filtres: FiltresResolus
    periode_precedente: PeriodeSuivi
    kpi: KpiSuivi
    kpi_precedent: KpiSuivi
    natures: list[RepartitionNature]
    reseaux: list[RepartitionReseau]


class LigneClassement(BaseModel):
    id: int | None = Field(None, description="Null : sans rattachement (« Non renseigné ») ou ligne « Autres »")
    code: str | None = None
    libelle: str
    nombre: int
    duree_heures: float
    end_mwh: float
    part: float


class ClassementSuivi(BaseModel):
    niveau: NiveauClassement
    total_interruptions: int
    lignes: list[LigneClassement]
    autres: LigneClassement | None = Field(None, description="Somme des lignes au-delà de la limite")


# ── Onglets Évolution et Réseau ───────────────────────────────────────────────────────────

Granularite = Literal["jour", "semaine", "mois"]
NiveauReseau = Literal["poste_source", "feeder"]


class NaturesPoint(BaseModel):
    """Nombre d'interruptions du point par catégorie de nature."""

    incident: int = 0
    delestage: int = 0
    travaux: int = 0
    autre: int = 0


class PointEvolution(BaseModel):
    debut: date
    fin: date
    libelle: str
    nombre: int
    duree_heures: float
    end_mwh: float
    natures: NaturesPoint


class EvolutionSuivi(BaseModel):
    granularite: Granularite
    points: list[PointEvolution] = Field(..., description="Tous les intervalles de la période, vides compris")


class LigneReseau(BaseModel):
    id: int | None = Field(None, description="Null : sans rattachement (« Non renseigné »)")
    code: str | None = None
    libelle: str
    poste_source: str | None = Field(None, description="Poste source du feeder (niveau feeder)")
    nombre: int
    duree_heures: float
    end_mwh: float
    coupures_clients: int
    postes_touches: int
    part: float


class ReseauSuivi(BaseModel):
    niveau: NiveauReseau
    total_interruptions: int
    lignes: list[LigneReseau]

