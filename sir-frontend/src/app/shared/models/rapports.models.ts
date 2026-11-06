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
  /** Formats produits ; « pdf » présent : aperçu possible dans la page. */
  formats: RapportFormat[];
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

/** Aperçu graphique d'un rapport : indicateurs comparés et séries pour les barres. */
export interface ApercuValeur {
  libelle: string;
  valeur: number;
  precedent: number | null;
}

export interface ApercuSerie {
  libelle: string;
  nombre: number;
  end_mwh: number;
  nombre_precedent: number | null;
  end_mwh_precedent: number | null;
  part_pct: number | null;
}

export interface ApercuHebdoDD {
  debut: string;
  fin: string;
  numero: number;
  numero_precedent: number;
  indicateurs: ApercuValeur[];
  categories: ApercuSerie[];
  services: ApercuSerie[];
  jours: ApercuSerie[];
}

export interface ApercuMensuelDistribution {
  annee: number;
  mois: number;
  region_id: number | null;
  indicateurs: ApercuValeur[];
  natures: ApercuSerie[];
  services: ApercuSerie[];
  /** Top des tops (permanent, semi-permanent, fugitif) par zone, avec le mois précédent. */
  top_feeders: ApercuSerie[];
  synthese: string[];
}
