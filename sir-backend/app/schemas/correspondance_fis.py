"""Schémas — correspondances FIS administrées (libellé FIS → entrée du Référentiel)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CategorieFis = Literal["nature", "cause", "siege", "signalisation"]


def normaliser_libelle_fis(libelle: str | None) -> str:
    """Libellé FIS normalisé : espace insécable remplacé, espaces de bord retirés, minuscules."""
    if libelle is None:
        return ""
    return libelle.replace("\xa0", " ").strip().lower()


class CorrespondanceFisCreate(BaseModel):
    categorie: CategorieFis
    libelle_fis: str = Field(..., min_length=1, max_length=200)
    referentiel_id: int = Field(..., gt=0)
    is_force_majeure: bool | None = Field(default=None, description="Cause seulement ; vide = règle de l'import")

    @field_validator("libelle_fis", mode="before")
    @classmethod
    def _normaliser(cls, valeur: object) -> object:
        return normaliser_libelle_fis(valeur) if isinstance(valeur, str) else valeur


class CorrespondanceFisResponse(BaseModel):
    id: int
    categorie: CategorieFis
    libelle_fis: str
    referentiel_id: int
    referentiel_code: str
    referentiel_libelle: str
    is_force_majeure: bool | None = None
    created_at: datetime | None = None
