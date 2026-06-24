export type StatutInterruption = 'en_cours' | 'cloture' | 'valide' | 'archive';

export type OuvertureInterruption = 'ouvert' | 'ferme';

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
  nature_libelle?: string | null;
  siege_libelle?: string | null;
  service_libelle?: string | null;
  poste_source_libelle?: string | null;
  feeder_libelle?: string | null;
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
  poste_source_id: number;
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

export interface WorkflowStepDeclenchement {
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
}

export interface WorkflowStepInterpellation {
  date_interpellation: string | null;
  date_arrivee: string | null;
  duree_minutes: number | null;
}

export interface WorkflowStepTronconnement {
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
  troncon_id: number | null;
  troncon_sig_id: number | null;
  noeud_amont_libelle: string | null;
  noeud_aval_libelle: string | null;
  troncon_libelle?: string | null;
  troncon_sig_libelle?: string | null;
}

export interface WorkflowStepLocalisation {
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
}

export interface WorkflowStepReparation {
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
}

export interface WorkflowStepRemise {
  date_debut: string | null;
  date_fin: string | null;
  duree_minutes: number | null;
}

export interface WorkflowStepClients {
  nombre_postes_impactes: number;
  nombre_clients_touches: number | null;
}

export interface InterruptionWorkflow {
  interruption_id: number;
  declenchement: WorkflowStepDeclenchement;
  interpellation: WorkflowStepInterpellation;
  tronconnement: WorkflowStepTronconnement;
  localisation: WorkflowStepLocalisation;
  reparation: WorkflowStepReparation;
  remise: WorkflowStepRemise;
  clients: WorkflowStepClients;
  responsable_matricule: number | null;
  observations_workflow: string | null;
}

export interface InterruptionWorkflowUpdate {
  declenchement?: Partial<Pick<WorkflowStepDeclenchement, 'date_debut' | 'date_fin'>>;
  interpellation?: Partial<Pick<WorkflowStepInterpellation, 'date_interpellation' | 'date_arrivee'>>;
  tronconnement?: Partial<
    Pick<
      WorkflowStepTronconnement,
      'date_debut' | 'date_fin' | 'troncon_id' | 'troncon_sig_id' | 'noeud_amont_libelle' | 'noeud_aval_libelle'
    >
  >;
  localisation?: Partial<Pick<WorkflowStepLocalisation, 'date_debut' | 'date_fin'>>;
  reparation?: Partial<Pick<WorkflowStepReparation, 'date_debut' | 'date_fin'>>;
  remise?: Partial<Pick<WorkflowStepRemise, 'date_debut' | 'date_fin'>>;
  responsable_matricule?: number | null;
  observations_workflow?: string | null;
}
