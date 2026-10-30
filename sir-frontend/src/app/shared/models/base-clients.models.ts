/** Base clients SAIFI/SAIDI — schémas backend app/schemas/base_clients.py */

export interface PeriodeContrats {
  annee: number;
  mois: number;
  ur: number;
  contrats: number;
  contrats_sans_agence: number;
  ur_rattachees: number;
  contrats_rattaches: number;
  date_maj: string | null;
  source: string;
}

export interface BaseClientsResume {
  periodes: PeriodeContrats[];
  /** Liens poste ↔ unité de relève par statut (valide, ajout_propose, suppression_proposee) */
  liens: Record<string, number>;
  bi_ods_configure: boolean;
}

export interface TacheLancee {
  task_id: string;
  message: string;
}

// ── Atelier : lien poste ↔ unité de relève ──────────────────────────────────

export type StatutLien = 'valide' | 'ajout_propose' | 'suppression_proposee';

export interface LienPosteUR {
  id: number;
  poste_id: number;
  poste_code: string;
  poste_libelle: string;
  service: string | null;
  unite_releve: string;
  ur_libelle: string | null;
  /** Contrats au dernier mois chargé ; null = UR absente de la base clients */
  nb_contrats: number | null;
  /** Postes qui se partagent l'UR */
  nb_postes: number | null;
  statut: StatutLien;
  modifie_par: string | null;
  modifie_le: string | null;
  valide_par: string | null;
  valide_le: string | null;
}

export interface LienPosteURCreate {
  poste_id: number;
  unite_releve: string;
}

export interface PosteRecherche {
  id: number;
  code: string;
  libelle: string;
  service: string | null;
  nombre_clients: number | null;
  nb_ur: number;
}

export interface UniteReleveRecherche {
  unite_releve: string;
  libelle: string | null;
  nb_contrats: number;
  nb_postes: number;
}

export interface DroitsAtelier {
  peut_proposer: boolean;
  peut_valider: boolean;
  /** Dernier mois chargé (MM/AAAA) */
  periode: string | null;
}

export interface ActionAtelier {
  id: number;
  message: string;
}

export interface LiensQuery {
  poste_id?: number;
  a_valider?: boolean;
  recherche?: string;
  page: number;
  page_size: number;
}
