export type RapportFormat = 'pdf' | 'xlsx' | 'docx';

export type RapportStatut = 'pending' | 'started' | 'success' | 'failure';

export type RapportDirection = 'distribution' | 'transport' | 'consolide';

export interface RapportJournalierRequest {
  date?: string;
  region_id?: number | null;
  format?: RapportFormat;
}

/** Semaine du lundi qui contient `date_debut` (défaut : semaine précédente). */
export interface RapportHebdomadaireRequest {
  date_debut?: string;
  region_id?: number | null;
  format?: RapportFormat;
}

/** Rapport hebdomadaire d'exploitation DD : semaine samedi → vendredi se terminant le `date_fin`
 * (défaut : dernière semaine complète). Word, Excel et PDF sont produits ; `format` choisit le téléchargement. */
export interface RapportHebdoDDRequest {
  date_fin?: string;
  format?: RapportFormat;
}

export interface RapportEnqueueResponse {
  task_id: string;
  type_rapport: string;
  statut: string;
  format: RapportFormat;
}

export interface RapportStatusResponse {
  task_id: string;
  type_rapport: string;
  format: RapportFormat;
  statut: RapportStatut;
  error_message: string | null;
  file_name: string | null;
  created_at: string;
  expires_at: string | null;
}

export interface RapportMensuelParams {
  annee: number;
  mois: number;
  region_id?: number;
  limit?: number;
  format?: RapportFormat;
}

export interface RapportAnnuelParams {
  annee: number;
  direction?: RapportDirection;
  region_id?: number;
  limit?: number;
  format?: RapportFormat;
}
