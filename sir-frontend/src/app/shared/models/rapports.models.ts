export type RapportFormat = 'pdf' | 'xlsx';

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
