"""Schémas — lecture d'un SMS pour pré-remplir la saisie d'une interruption de distribution."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EvenementSms = Literal["apparition", "remise", "inconnu"]


class LectureSmsRequest(BaseModel):
    texte: str = Field(..., min_length=1, max_length=1000)


class DepartReconnu(BaseModel):
    id: int
    libelle: str
    poste_source_id: int
    poste_source_libelle: str
    region_id: int | None = None


class InterruptionEnCours(BaseModel):
    id: int
    numero_interruption: int
    date_apparition: datetime


class LectureSmsResponse(BaseModel):
    """Ce que SIRV2 a reconnu dans le SMS ; l'agent vérifie et complète à l'écran."""

    texte: str
    evenement: EvenementSms
    date_apparition: datetime | None = None
    date_remise: datetime | None = None
    depart: DepartReconnu | None = None
    # Plusieurs départs possibles (même nom sur plusieurs postes sources) : choix à l'écran
    departs_possibles: list[DepartReconnu] = []
    cause_id: int | None = None
    cause_libelle: str | None = None
    is_programme: bool = False
    # Remise : interruption à clôturer · apparition : interruption déjà ouverte (doublon ?)
    interruption_en_cours: InterruptionEnCours | None = None
    # Départ reconnu mais hors de la région du compte (BCC → Dakar, BRC → Régions)
    hors_perimetre: bool = False
    champs_reconnus: list[str] = []
    confiance: float = 0.0
