from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

StatutInterruption = Literal["en_cours", "cloture", "valide", "archive"]

CREATE_ROLES = frozenset({"BCC", "BRC", "ADMIN_SCR"})


class InterruptionDistributionCreate(BaseModel):
    date_apparition: datetime
    poste_source_id: int = Field(..., ge=1)
    feeder_id: int = Field(..., ge=1)
    sous_feeder_id: int | None = Field(default=None, ge=1)
    cause_id: int = Field(..., ge=1)
    nature_id: int = Field(..., ge=1)
    siege_id: int = Field(..., ge=1)
    signalisation_id: int = Field(..., ge=1)
    type_end_id: int = Field(..., ge=1)
    type_reseau_id: int = Field(..., ge=1)
    puissance_coupee_mw: float | None = Field(default=None, ge=0)
    localisation: str | None = Field(default=None, max_length=500)
    observations: str | None = Field(default=None, max_length=2000)
    is_force_majeure: bool = False
    is_fugitive: bool = False
    entreprise_id: int | None = Field(default=None, ge=1)
    prestataire_id: int | None = Field(default=None, ge=1)
    tension_kv: float | None = Field(default=None, ge=0)
    nombre_clients_mt: int | None = Field(default=None, ge=0)
    nombre_clients_bt: int | None = Field(default=None, ge=0)
    is_programme: bool = False
    has_extension_bt: bool = False


class InterruptionDistributionUpdate(BaseModel):
    date_apparition: datetime | None = None
    cause_id: int | None = Field(default=None, ge=1)
    nature_id: int | None = Field(default=None, ge=1)
    siege_id: int | None = Field(default=None, ge=1)
    signalisation_id: int | None = Field(default=None, ge=1)
    type_end_id: int | None = Field(default=None, ge=1)
    type_reseau_id: int | None = Field(default=None, ge=1)
    puissance_coupee_mw: float | None = Field(default=None, ge=0)
    localisation: str | None = Field(default=None, max_length=500)
    observations: str | None = Field(default=None, max_length=2000)
    is_force_majeure: bool | None = None
    is_fugitive: bool | None = None
    entreprise_id: int | None = Field(default=None, ge=1)
    prestataire_id: int | None = Field(default=None, ge=1)
    tension_kv: float | None = Field(default=None, ge=0)
    nombre_clients_mt: int | None = Field(default=None, ge=0)
    nombre_clients_bt: int | None = Field(default=None, ge=0)
    is_programme: bool | None = None
    has_extension_bt: bool | None = None


class InterruptionClotureRequest(BaseModel):
    date_remise: datetime


OuvertureInterruption = Literal["ouvert", "ferme"]


class InterruptionDistributionFilters(BaseModel):
    region_id: int | None = Field(default=None, ge=1)
    service_id: int | None = Field(default=None, ge=1)
    feeder_id: int | None = Field(default=None, ge=1)
    nature_id: int | None = Field(default=None, ge=1)
    ouverture: OuvertureInterruption | None = None
    statut: StatutInterruption | None = None
    date_debut: datetime | None = None
    date_fin: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class InterruptionDistributionStatsResponse(BaseModel):
    total: int
    non_validees: int
    en_cours: int


class InterruptionDistributionResponse(BaseModel):
    id: int
    numero_interruption: int
    type_direction: Literal["distribution"]
    direction_source_id: int | None = None
    statut: StatutInterruption
    statut_id: int | None = None
    entreprise_id: int | None = None
    prestataire_id: int | None = None
    service_id: int | None
    feeder_id: int | None
    sous_feeder_id: int | None = None
    poste_source_id: int | None
    date_apparition: datetime
    date_remise: datetime | None
    duree_minutes: int | None
    cause_id: int | None
    nature_id: int | None
    siege_id: int | None
    signalisation_id: int | None
    type_end_id: int | None = None
    type_reseau_id: int | None = None
    puissance_coupee_mw: float | None
    localisation: str | None
    observations: str | None
    is_force_majeure: bool
    is_fugitive: bool
    tension_kv: float | None = None
    nombre_clients_mt: int | None = None
    nombre_clients_bt: int | None = None
    end_mwh: float | None = None
    is_programme: bool = False
    has_extension_bt: bool = False
    created_by_id: int
    updated_by_id: int | None = None
    created_at: datetime
    updated_at: datetime
    entreprise_libelle: str | None = None
    prestataire_libelle: str | None = None
    cause_libelle: str | None = None
    nature_libelle: str | None = None
    siege_libelle: str | None = None
    service_libelle: str | None = None
    poste_source_libelle: str | None = None
    feeder_libelle: str | None = None
    sous_feeder_libelle: str | None = None
    type_end_libelle: str | None = None
    type_reseau_libelle: str | None = None
    region_libelle: str | None = None

    # Renseignée dans les listes pour les interruptions clôturées (file de validation)
    date_cloture: datetime | None = None

    model_config = {"from_attributes": True}


class PosteImpacteResponse(BaseModel):
    poste_id: int
    poste_code: str | None = None
    poste_libelle: str | None = None
    nombre_clients_touches: int | None = None
    date_interruption: datetime | None = None
    feeder_id: int | None = None
    service_id: int | None = None
    poste_source_id: int | None = None


class PosteInterruptionCreate(BaseModel):
    poste_id: int = Field(..., ge=1)
    nombre_clients_touches: int | None = Field(default=None, ge=0)
    date_interruption: datetime | None = None


class PosteImpacteFromSigRequest(BaseModel):
    troncon_sig_id: int | None = Field(default=None, ge=1)
    chain_limit: int = Field(default=3, ge=1, le=10)


class PosteImpacteBulkResponse(BaseModel):
    added_count: int
    skipped_count: int
    items: list[PosteImpacteResponse] = Field(default_factory=list)


class UtilisateurSummaryResponse(BaseModel):
    id: int
    login: str
    nom: str
    prenom: str


class EnergieNdSummaryResponse(BaseModel):
    valeur_mwh: float
    puissance_coupee_mw: float
    duree_heures: float
    est_force_majeure: bool
    calculated_at: datetime


class InterruptionDistributionDetailResponse(InterruptionDistributionResponse):
    feeder_libelle: str | None = None
    cause_libelle: str | None = None
    nature_libelle: str | None = None
    siege_libelle: str | None = None
    signalisation_libelle: str | None = None
    service_code: str | None = None
    service_libelle: str | None = None
    postes_impactes: list[PosteImpacteResponse] = Field(default_factory=list)
    energie_nd: EnergieNdSummaryResponse | None = None
    created_by: UtilisateurSummaryResponse | None = None
    validated_by: UtilisateurSummaryResponse | None = None
    validated_by_id: int | None = None
    updated_by: UtilisateurSummaryResponse | None = None
