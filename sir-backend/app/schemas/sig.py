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


# ── Administration → SIG (consultation) ─────────────────────────────────────────


class CategorieSigResponse(BaseModel):
    categorie: str
    nombre: int


class SyntheseSigResponse(BaseModel):
    noeuds: int
    noeuds_localises: int
    noeuds_rattaches: int
    troncons: int
    longueur_km: float
    feeders_sig: int
    feeders_rattaches: int
    stations: int
    dernier_chargement: datetime | None = None
    categories: list[CategorieSigResponse] = Field(default_factory=list)


class StationSigResponse(BaseModel):
    """Station (poste source) du SIG, déduite des nœuds."""

    station: str
    noeuds: int
    feeders: int
    latitude: float | None = None
    longitude: float | None = None
    poste_source_sirv2: str | None = None


class FeederSigResponse(BaseModel):
    """Départ du SIG (dernier chargement) et son rattachement au référentiel SIRV2."""

    nom_feeder: str
    troncons: int
    longueur_km: float
    tension_kv: float | None = None
    noeuds: int = 0
    noeuds_localises: int = 0
    feeder_id: int | None = None
    feeder_libelle: str | None = None
    poste_source_libelle: str | None = None
    date_chargement: datetime | None = None


class TronconSigAdminResponse(BaseModel):
    id: int
    nom_troncon: str | None = None
    nom_feeder: str | None = None
    feeder_id: int | None = None
    nom_noeud_amont: str | None = None
    code_noeud_amont: str | None = None
    nom_noeud_aval: str | None = None
    code_noeud_aval: str | None = None
    tension_kv: float | None = None
    longueur_m: float | None = None
    date_chargement: datetime | None = None


class NoeudSigAdminResponse(BaseModel):
    id: int
    legacy_fid: int
    nom: str | None = None
    nom_feeder: str | None = None
    feeder_id: int | None = None
    station: str | None = None
    categorie: str | None = None
    coord_x: float | None = None
    coord_y: float | None = None
    latitude: float | None = None
    longitude: float | None = None
