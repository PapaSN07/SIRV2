"""Schémas unifilaires : réponses de l'API."""

from datetime import datetime

from pydantic import BaseModel, Field


class SchemaUnifilaireResponse(BaseModel):
    id: int
    nom: str
    fichier: str
    region_id: int | None
    region_libelle: str | None = None
    largeur: float
    hauteur: float
    zoom_max: int
    nb_postes: int
    importe_le: datetime


class PosteSchemaResponse(BaseModel):
    """Poste du schéma : symbole et libellé (points PDF, origine en haut à gauche)."""

    id: int
    rang: int
    libelle: str | None
    forme: str
    puissance_kva: int | None
    x0: float
    y0: float
    x1: float
    y1: float
    lx0: float | None
    ly0: float | None
    lx1: float | None
    ly1: float | None
    poste_id: int | None
    poste_code: str | None = None
    poste_libelle: str | None = None
    rapprochement: str | None


class PostesEntreRequest(BaseModel):
    debut_id: int = Field(ge=1, description="Poste du schéma où commence la section")
    fin_id: int = Field(ge=1, description="Poste du schéma où finit la section")


class DerivationResponse(BaseModel):
    depuis_id: int | None = Field(description="Poste du chemin d'où part la dérivation (repère)")
    postes: list[PosteSchemaResponse]


class PostesEntreResponse(BaseModel):
    """Postes entre deux postes : le long de la ligne, en antenne, et dérivations à choisir."""

    chemin: list[PosteSchemaResponse]
    antennes: list[PosteSchemaResponse]
    derivations: list[DerivationResponse]
    postes_hors_limite: int
    trace: list[tuple[float, float]]


class AssociationPosteRequest(BaseModel):
    poste_id: int | None = Field(default=None, ge=1, description="Poste SIRV2 ; null pour dissocier")
