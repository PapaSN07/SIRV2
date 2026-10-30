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
