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
