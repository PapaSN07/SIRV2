export type StatutInterruption = 'en_cours' | 'cloture' | 'valide' | 'archive';

export interface InterruptionDistribution {
  id: number;
  numero_interruption: number;
  type_direction: 'distribution';
  statut: StatutInterruption;
  service_id: number | null;
  feeder_id: number | null;
  poste_source_id: number | null;
  date_apparition: string;
  date_remise: string | null;
  duree_minutes: number | null;
  cause_id: number | null;
  nature_id: number | null;
  siege_id: number | null;
  signalisation_id: number | null;
  puissance_coupee_mw: number | null;
  localisation: string | null;
  observations: string | null;
  is_force_majeure: boolean;
  is_fugitive: boolean;
  tension_kv: number | null;
  nombre_clients_mt: number | null;
  nombre_clients_bt: number | null;
  end_mwh: number | null;
  is_programme: boolean;
  has_extension_bt: boolean;
  created_by_id: number;
  created_at: string;
  updated_at: string;
  cause_libelle?: string | null;
  region_libelle?: string | null;
}

export interface UtilisateurSummary {
  id: number;
  login: string;
  nom: string;
  prenom: string;
}

export interface EnergieNdSummary {
  valeur_mwh: number;
  puissance_coupee_mw: number;
  duree_heures: number;
  est_force_majeure: boolean;
  calculated_at: string;
}

export interface PosteImpacte {
  poste_id: number;
  poste_code: string | null;
  poste_libelle: string | null;
  nombre_clients_touches: number | null;
}

export interface InterruptionDistributionDetail extends InterruptionDistribution {
  feeder_libelle: string | null;
  cause_libelle: string | null;
  nature_libelle: string | null;
  siege_libelle: string | null;
  signalisation_libelle: string | null;
  service_code: string | null;
  service_libelle: string | null;
  postes_impactes: PosteImpacte[];
  energie_nd: EnergieNdSummary | null;
  created_by: UtilisateurSummary | null;
  validated_by: UtilisateurSummary | null;
  validated_by_id: number | null;
}

export interface InterruptionDistributionCreate {
  date_apparition: string;
  feeder_id: number;
  cause_id: number;
  nature_id: number;
  siege_id: number;
  signalisation_id: number;
  puissance_coupee_mw?: number | null;
  localisation?: string | null;
  observations?: string | null;
  is_force_majeure?: boolean;
  is_fugitive?: boolean;
  tension_kv?: number | null;
  nombre_clients_mt?: number | null;
  nombre_clients_bt?: number | null;
  is_programme?: boolean;
  has_extension_bt?: boolean;
}

export interface InterruptionDistributionUpdate {
  date_apparition?: string;
  cause_id?: number;
  nature_id?: number;
  siege_id?: number;
  signalisation_id?: number;
  puissance_coupee_mw?: number | null;
  localisation?: string | null;
  observations?: string | null;
  is_force_majeure?: boolean;
  is_fugitive?: boolean;
  tension_kv?: number | null;
  nombre_clients_mt?: number | null;
  nombre_clients_bt?: number | null;
  is_programme?: boolean;
  has_extension_bt?: boolean;
}

export interface InterruptionClotureRequest {
  date_remise: string;
}

export interface PosteInterruptionCreate {
  poste_id: number;
  nombre_clients_touches?: number | null;
}

export interface InterruptionListParams {
  page?: number;
  page_size?: number;
  region_id?: number;
  feeder_id?: number;
  statut?: StatutInterruption;
  date_debut?: string;
  date_fin?: string;
}
