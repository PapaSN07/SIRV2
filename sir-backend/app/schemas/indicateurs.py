"""Schemas Pydantic -- indicateurs CRSE (Sprint 5)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class SaifiSaidiCalculationResult(BaseModel):
    interruption_id: int
    service_id: int | None = None
    annee: int | None = None
    mois: int | None = None
    status: str
    saifi: float | None = None
    saidi: float | None = None
    nombre_interruptions: int | None = None
    total_clients_reference: int | None = None
    region_id: int | None = None


class SaifiSaidiRecordResponse(BaseModel):
    service_id: int
    annee: int
    mois: int
    saifi: float
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int
    calculated_at: datetime

    model_config = {"from_attributes": True}


class SaifiSaidiAggregateResponse(BaseModel):
    niveau: str = Field(..., description="service | delegation | region | national")
    scope_id: int | None = None
    annee: int
    mois: int
    saifi: float
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int


class EndServiceItemResponse(BaseModel):
    service_id: int
    end_mwh: float
    nombre_interruptions: int


class EndAggregateResponse(BaseModel):
    niveau: str = Field(..., description="service | delegation | region | national")
    scope_id: int | None = None
    annee: int
    mois: int
    end_mwh: float
    nombre_interruptions: int


class SaifiServiceItemResponse(BaseModel):
    service_id: int
    saifi: float
    nombre_interruptions: int
    total_clients_reference: int


class SaidiServiceItemResponse(BaseModel):
    service_id: int
    saidi: float
    nombre_interruptions: int
    total_clients_reference: int


class EndIndicateurResponse(BaseModel):
    aggregate: EndAggregateResponse
    services: PaginatedResponse[EndServiceItemResponse] | None = None


class SaifiIndicateurResponse(BaseModel):
    aggregate: SaifiSaidiAggregateResponse
    services: PaginatedResponse[SaifiServiceItemResponse] | None = None


class SaidiIndicateurResponse(BaseModel):
    aggregate: SaifiSaidiAggregateResponse
    services: PaginatedResponse[SaidiServiceItemResponse] | None = None


class CauseRepartitionItemResponse(BaseModel):
    label: str
    nombre: int
    percent: float


class NatureRepartitionItemResponse(BaseModel):
    """Repartition par nature -- format Tableau de Bord FIS."""

    code: str
    libelle: str
    nombre: int
    end_kwh: float
    percent: float


class NatureServiceCellResponse(BaseModel):
    nombre: int
    end_kwh: float


class NatureServiceColumnResponse(BaseModel):
    service_id: int
    code: str
    libelle: str
    nombre: int
    end_kwh: float


class NatureServiceLigneResponse(BaseModel):
    code: str
    libelle: str
    cellules: list[NatureServiceCellResponse]
    nombre: int
    end_kwh: float


class NatureServiceRepartitionResponse(BaseModel):
    """END et nombre d'interruptions croisés par nature et par service."""

    services: list[NatureServiceColumnResponse] = Field(default_factory=list)
    lignes: list[NatureServiceLigneResponse] = Field(default_factory=list)
    total_nombre: int = 0
    total_end_kwh: float = 0


class TableauDeBordResponse(BaseModel):
    niveau: str
    scope_id: int | None = None
    annee: int
    mois: int
    end_mois: float
    saifi: float
    saidi: float
    nb_interruptions_actives: int
    nb_interruptions_mois: int
    causes_repartition: list[CauseRepartitionItemResponse] = Field(default_factory=list)
    natures_repartition: list[NatureRepartitionItemResponse] = Field(default_factory=list)
    nature_service: NatureServiceRepartitionResponse = Field(
        default_factory=NatureServiceRepartitionResponse
    )


class HistoriquePointResponse(BaseModel):
    annee: int
    mois: int
    valeur: float


class HistoriqueResponse(BaseModel):
    type: str = Field(..., description="end | saifi | saidi")
    niveau: str
    scope_id: int | None = None
    annees: int
    points: list[HistoriquePointResponse]


class TopFeederItemResponse(BaseModel):
    feeder_id: int
    code: str
    libelle: str
    service_id: int | None = None
    end_mwh: float
    nombre_interruptions: int


class TopFeedersResponse(BaseModel):
    niveau: str
    scope_id: int | None = None
    annee: int
    mois: int
    limit: int
    items: list[TopFeederItemResponse]


class Defauts100KmResponse(BaseModel):
    nombre_defauts: int
    longueur_km: float
    valeur: float | None = None


class IndicateurSuiviResponse(BaseModel):
    code: str
    libelle: str
    unite: str
    objectif_annuel: float | None = None
    objectif_journalier: float | None = None
    realise_jour: float | None = None
    ecart_jour: float | None = None
    taux_jour: float | None = None
    note_jour: str = ""
    objectif_cumul: float | None = None
    realise_cumul: float | None = None
    ecart_cumul: float | None = None
    taux_cumul: float | None = None
    note_cumul: str = ""


class PosteOuvertResponse(BaseModel):
    poste_id: int
    code: str
    libelle: str
    interruption_id: int
    numero_interruption: int
    date_apparition: datetime
    feeder_libelle: str | None = None
    service_libelle: str | None = None
    sans_remise: bool = False
    latitude: float | None = None
    longitude: float | None = None


class TopPosteResponse(BaseModel):
    poste_id: int
    code: str
    libelle: str
    nombre: int
    clients: int
    end_mwh: float


class ZonePerturbeeResponse(BaseModel):
    zone_id: int
    code: str
    libelle: str
    nombre: int
    end_mwh: float
    saifi: float | None = None
    saidi: float | None = None


class PilotageResponse(BaseModel):
    niveau: str
    scope_id: int | None = None
    annee: int
    mois: int
    annee_objectif: int
    jour: str
    jours_ecoules: int
    jours_annee: int
    peut_modifier_objectifs: bool
    defauts_100km_mois: Defauts100KmResponse
    indicateurs: list[IndicateurSuiviResponse]
    postes_ouverts: list[PosteOuvertResponse]
    top_postes: list[TopPosteResponse]
    top_feeders: list[TopFeederItemResponse]
    zone_niveau: str
    zones: list[ZonePerturbeeResponse]


class ObjectifsPilotageUpdate(BaseModel):
    annee: int = Field(..., ge=2000, le=2100)
    end_mwh: float | None = Field(default=None, ge=0)
    saifi: float | None = Field(default=None, ge=0)
    saidi: float | None = Field(default=None, ge=0)
    defauts_100km: float | None = Field(default=None, ge=0)


class TendancePointResponse(BaseModel):
    annee: int
    mois: int
    nombre: int
    end_kwh: float
    tendance_nombre: float


class TendanceResponse(BaseModel):
    cible: str
    cible_id: int
    code: str
    libelle: str
    annees: int
    sens: str
    pente_mensuelle: float
    lecture: str
    points: list[TendancePointResponse]
    previsions: list[TendancePointResponse]
