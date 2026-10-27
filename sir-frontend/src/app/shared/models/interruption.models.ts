export type StatutInterruption = 'en_cours' | 'cloture' | 'valide' | 'archive';

export type OuvertureInterruption = 'ouvert' | 'ferme';

export interface InterruptionDistribution {
  id: number;
  /** Listes : date de clôture des interruptions en attente de validation. */
  date_cloture?: string | null;
  numero_interruption: number;
  type_direction: 'distribution';
  direction_source_id?: number | null;
  statut: StatutInterruption;
  statut_id?: number | null;
  entreprise_id?: number | null;
  prestataire_id?: number | null;
  entreprise_libelle?: string | null;
  prestataire_libelle?: string | null;
  service_id: number | null;
  feeder_id: number | null;
  sous_feeder_id: number | null;
  poste_source_id: number | null;
  date_apparition: string;
  date_remise: string | null;
  duree_minutes: number | null;
  cause_id: number | null;
  nature_id: number | null;
  siege_id: number | null;
  signalisation_id: number | null;
  type_end_id?: number | null;
  type_reseau_id?: number | null;
  type_end_libelle?: string | null;
  type_reseau_libelle?: string | null;
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
  updated_by_id?: number | null;
  created_at: string;
  updated_at: string;
  cause_libelle?: string | null;
  nature_libelle?: string | null;
  siege_libelle?: string | null;
  service_libelle?: string | null;
  poste_source_libelle?: string | null;
  feeder_libelle?: string | null;
  sous_feeder_libelle?: string | null;
  region_libelle?: string | null;
}

export interface InterruptionDistributionStats {
  total: number;
  non_validees: number;
  en_cours: number;
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
  date_interruption?: string | null;
  feeder_id?: number | null;
  service_id?: number | null;
  poste_source_id?: number | null;
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
  updated_by: UtilisateurSummary | null;
}

export interface InterruptionDistributionCreate {
  date_apparition: string;
  poste_source_id: number;
  feeder_id: number;
  sous_feeder_id?: number | null;
  cause_id: number;
  nature_id: number;
  siege_id: number;
  signalisation_id: number;
  type_end_id: number;
  type_reseau_id: number;
  puissance_coupee_mw?: number | null;
  localisation?: string | null;
  observations?: string | null;
  is_force_majeure?: boolean;
  is_fugitive?: boolean;
  entreprise_id?: number | null;
  prestataire_id?: number | null;
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
  type_end_id?: number;
  type_reseau_id?: number;
  puissance_coupee_mw?: number | null;
  localisation?: string | null;
  observations?: string | null;
  is_force_majeure?: boolean;
  is_fugitive?: boolean;
  entreprise_id?: number | null;
  prestataire_id?: number | null;
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
  date_interruption?: string | null;
}

export interface PosteImpacteBulk {
  added_count: number;
  skipped_count: number;
  items: PosteImpacte[];
}

export interface PosteImpacteFromSigRequest {
  troncon_sig_id?: number | null;
  chain_limit?: number;
}

export interface InterruptionListParams {
  page?: number;
  page_size?: number;
  region_id?: number;
  service_id?: number;
  feeder_id?: number;
  nature_id?: number;
  ouverture?: OuvertureInterruption;
  statut?: StatutInterruption;
  date_debut?: string;
  date_fin?: string;
}

export type WorkflowEtat = 'terminee' | 'active' | 'verrouillee';

export interface WorkflowEtape {
  etape_workflow_id: number;
  code: string;
  libelle_etape_workflow: string;
  ordre: number;
  etape_suivante_id: number | null;
  etat: WorkflowEtat;
  workflow_id: number | null;
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
  observation: string | null;
  responsable_matricule: number | null;
  troncon_id: number | null;
  troncon_sig_id: number | null;
  noeud_amont_libelle: string | null;
  noeud_aval_libelle: string | null;
  troncon_libelle: string | null;
  troncon_sig_libelle: string | null;
}

export interface WorkflowStepClients {
  nombre_postes_impactes: number;
  nombre_clients_touches: number | null;
}

export interface InterruptionWorkflow {
  interruption_id: number;
  etapes: WorkflowEtape[];
  clients: WorkflowStepClients;
}

export interface WorkflowEtapeUpdate {
  date_debut?: string | null;
  date_fin?: string | null;
  observation?: string | null;
  responsable_matricule?: number | null;
  troncon_id?: number | null;
  troncon_sig_id?: number | null;
  noeud_amont_libelle?: string | null;
  noeud_aval_libelle?: string | null;
}

export const ETAPE_TRONCONNEMENT = 'tronconnement';

export function tronconSigIdFromWorkflow(wf: InterruptionWorkflow | null): number | null {
  return wf?.etapes.find((e) => e.code === ETAPE_TRONCONNEMENT)?.troncon_sig_id ?? null;
}

/** Cycle de vie : une ligne par changement de statut (frise de la fiche). */
export type ActionStatut =
  | 'creation'
  | 'cloture'
  | 'validation'
  | 'renvoi_correction'
  | 'devalidation'
  | 'archivage';

export interface StatutHistorique {
  id: number;
  action: ActionStatut;
  ancien_statut: StatutInterruption | null;
  nouveau_statut: StatutInterruption;
  motif: string | null;
  utilisateur_id: number;
  utilisateur_nom: string | null;
  created_at: string;
}

export interface MotifRequest {
  motif: string;
}

export interface ValidationLotResponse {
  validees: number[];
  echecs: { id: number; erreur: string }[];
}

export interface ArchivageRequest {
  annee: number;
  mois: number;
}

export interface ArchivageResponse {
  annee: number;
  mois: number;
  archivees: number;
  non_validees_restantes: number;
}
