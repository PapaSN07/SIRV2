import {
  EnergieNdSummary,
  InterruptionClotureRequest,
  StatutInterruption,
  UtilisateurSummary,
} from './interruption.models';

export type { InterruptionClotureRequest, StatutInterruption, UtilisateurSummary, EnergieNdSummary };

export type TypeDirectionTransport = 'transport' | 'omvg';

export interface InterruptionTransport {
  id: number;
  numero_interruption: number;
  type_direction: TypeDirectionTransport;
  statut: StatutInterruption;
  service_id: number | null;
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
  equipement_transport_id: number | null;
  source_transport_id: number | null;
  puissance_transit_mw: number | null;
  energie_non_fournie_mwh: number | null;
  created_by_id: number;
  created_at: string;
  updated_at: string;
}

export interface InterruptionTransportDetail extends InterruptionTransport {
  equipement_libelle: string | null;
  source_libelle: string | null;
  cause_libelle: string | null;
  nature_libelle: string | null;
  siege_libelle: string | null;
  signalisation_libelle: string | null;
  energie_nd: EnergieNdSummary | null;
  created_by: UtilisateurSummary | null;
  validated_by: UtilisateurSummary | null;
  validated_by_id: number | null;
}

export interface InterruptionTransportCreate {
  type_direction?: TypeDirectionTransport;
  date_apparition: string;
  equipement_transport_id: number;
  source_transport_id?: number | null;
  poste_ligne_id?: number | null;
  cause_id: number;
  nature_id: number;
  siege_id: number;
  signalisation_id: number;
  tension_kv?: number | null;
  puissance_transit_mw?: number | null;
  puissance_coupee_mw?: number | null;
  localisation?: string | null;
  observations?: string | null;
  is_force_majeure?: boolean;
  is_fugitive?: boolean;
}

export interface InterruptionTransportUpdate {
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
  puissance_transit_mw?: number | null;
  source_transport_id?: number | null;
}

export interface InterruptionTransportListParams {
  page?: number;
  page_size?: number;
  type_direction?: TypeDirectionTransport;
  statut?: StatutInterruption;
  date_debut?: string;
  date_fin?: string;
  equipement_transport_id?: number;
  source_transport_id?: number;
}
