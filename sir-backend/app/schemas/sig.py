"""Schémas Pydantic — topologie SIG."""

from datetime import datetime

from pydantic import BaseModel, Field


class NoeudSigResponse(BaseModel):
    id: int
    legacy_fid: int
    nom: str | None
    nom_feeder: str | None
    feeder_id: int | None
    station: str | None
    coord_x: float | None
    coord_y: float | None
    categorie: str | None

    model_config = {"from_attributes": True}


class TronconSigResponse(BaseModel):
    id: int
    legacy_id: int
    legacy_fid: int | None
    nom_feeder: str | None
    feeder_id: int | None
    nom_troncon: str | None
    nom_noeud_amont: str | None
    code_noeud_amont: str | None
    nom_noeud_aval: str | None
    code_noeud_aval: str | None
    tension_kv: float | None
    longueur_m: float | None
    date_chargement: datetime | None

    model_config = {"from_attributes": True}


class TronconSigChaineResponse(BaseModel):
    troncon: TronconSigResponse
    chaine_aval: list[TronconSigResponse] = Field(default_factory=list)
