import { PaginatedResponse } from './api.models';

export interface TableauDeBordResponse {
  niveau: string;
  scope_id: number | null;
  annee: number;
  mois: number;
  end_mois: number;
  saifi: number;
  saidi: number;
  nb_interruptions_actives: number;
  nb_interruptions_mois: number;
  causes_repartition?: CauseRepartitionItem[];
  natures_repartition?: NatureRepartitionItem[];
  nature_service?: NatureServiceRepartition;
}

export interface NatureServiceCell {
  nombre: number;
  end_kwh: number;
}

export interface NatureServiceColumn {
  service_id: number;
  code: string;
  libelle: string;
  nombre: number;
  end_kwh: number;
}

export interface NatureServiceLigne {
  code: string;
  libelle: string;
  cellules: NatureServiceCell[];
  nombre: number;
  end_kwh: number;
}

export interface NatureServiceRepartition {
  services: NatureServiceColumn[];
  lignes: NatureServiceLigne[];
  total_nombre: number;
  total_end_kwh: number;
}

export interface HistoriquePoint {
  annee: number;
  mois: number;
  valeur: number;
}

export type IndicateurHistoriqueType = 'end' | 'saifi' | 'saidi';

export interface HistoriqueResponse {
  type: IndicateurHistoriqueType;
  niveau: string;
  scope_id: number | null;
  annees: number;
  points: HistoriquePoint[];
}

export interface EndAggregate {
  niveau: string;
  scope_id: number | null;
  annee: number;
  mois: number;
  end_mwh: number;
  nombre_interruptions: number;
}

export interface SaifiSaidiAggregate {
  niveau: string;
  scope_id: number | null;
  annee: number;
  mois: number;
  saifi: number;
  saidi: number;
  nombre_interruptions: number;
  total_clients_reference: number;
}

export interface EndIndicateurResponse {
  aggregate: EndAggregate;
  services: PaginatedResponse<{ service_id: number; end_mwh: number; nombre_interruptions: number }> | null;
}

export interface SaifiIndicateurResponse {
  aggregate: SaifiSaidiAggregate;
  services: PaginatedResponse<{
    service_id: number;
    saifi: number;
    nombre_interruptions: number;
    total_clients_reference: number;
  }> | null;
}

export interface SaidiIndicateurResponse {
  aggregate: SaifiSaidiAggregate;
  services: PaginatedResponse<{
    service_id: number;
    saidi: number;
    nombre_interruptions: number;
    total_clients_reference: number;
  }> | null;
}

export interface TopFeederItem {
  feeder_id: number;
  code: string;
  libelle: string;
  service_id: number | null;
  end_mwh: number;
  nombre_interruptions: number;
}

export interface TopFeedersResponse {
  niveau: string;
  scope_id: number | null;
  annee: number;
  mois: number;
  limit: number;
  items: TopFeederItem[];
}

export interface IndicateursQueryParams {
  annee?: number;
  mois?: number;
  periode?: string;
  region_id?: number;
}

/** Répartition par cause — fournie par le tableau de bord API. */
export interface CauseRepartitionItem {
  label: string;
  nombre: number;
  percent: number;
  color?: string;
}

/** Répartition par nature FIS — fournie par le tableau de bord API. */
export interface NatureRepartitionItem {
  code: string;
  libelle: string;
  nombre: number;
  end_kwh: number;
  percent: number;
}

export interface Defauts100Km {
  nombre_defauts: number;
  longueur_km: number;
  valeur: number | null;
}

export interface IndicateurSuivi {
  code: string;
  libelle: string;
  unite: string;
  objectif_annuel: number | null;
  objectif_journalier: number | null;
  realise_jour: number | null;
  ecart_jour: number | null;
  taux_jour: number | null;
  note_jour: string;
  objectif_cumul: number | null;
  realise_cumul: number | null;
  ecart_cumul: number | null;
  taux_cumul: number | null;
  note_cumul: string;
}

export interface PosteOuvertCarte {
  poste_id: number;
  code: string;
  libelle: string;
  interruption_id: number;
  numero_interruption: number;
  date_apparition: string;
  feeder_libelle: string | null;
  service_libelle: string | null;
  sans_remise: boolean;
  latitude: number | null;
  longitude: number | null;
}

export interface TopPosteItem {
  poste_id: number;
  code: string;
  libelle: string;
  nombre: number;
  clients: number;
  end_mwh: number;
}

export interface ZonePerturbee {
  zone_id: number;
  code: string;
  libelle: string;
  nombre: number;
  end_mwh: number;
  saifi: number | null;
  saidi: number | null;
}

export interface PilotageResponse {
  niveau: string;
  scope_id: number | null;
  annee: number;
  mois: number;
  annee_objectif: number;
  jour: string;
  jours_ecoules: number;
  jours_annee: number;
  peut_modifier_objectifs: boolean;
  defauts_100km_mois: Defauts100Km;
  indicateurs: IndicateurSuivi[];
  postes_ouverts: PosteOuvertCarte[];
  top_postes: TopPosteItem[];
  top_feeders: TopFeederItem[];
  zone_niveau: string;
  zones: ZonePerturbee[];
}

export interface ObjectifsPilotageUpdate {
  annee: number;
  end_mwh?: number;
  saifi?: number;
  saidi?: number;
  defauts_100km?: number;
}

export interface TendancePoint {
  annee: number;
  mois: number;
  nombre: number;
  end_kwh: number;
  tendance_nombre: number;
}

export interface TendanceResponse {
  cible: 'feeder' | 'poste' | string;
  cible_id: number;
  code: string;
  libelle: string;
  annees: number;
  sens: string;
  pente_mensuelle: number;
  lecture: string;
  points: TendancePoint[];
  previsions: TendancePoint[];
}
