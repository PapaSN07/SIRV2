export type NaptStatut = 'brouillon' | 'soumis' | 'approuve' | 'rejete' | 'archive';

export interface NaptItem {
  id: number;
  numero_napt: string;
  service_id: number;
  feeder_id: number | null;
  statut: NaptStatut;
  objet_travaux: string;
  date_debut_prevue: string;
  date_fin_prevue: string;
  date_debut_reelle: string | null;
  date_fin_reelle: string | null;
  is_interruption_necessaire: boolean;
  observations: string | null;
  created_by_id: number;
  approved_by_id: number | null;
  created_at: string;
  updated_at: string;
  service_libelle: string | null;
  feeder_libelle: string | null;
}

export interface NaptCreate {
  service_id: number;
  feeder_id?: number | null;
  objet_travaux: string;
  date_debut_prevue: string;
  date_fin_prevue: string;
  is_interruption_necessaire?: boolean;
  observations?: string | null;
}
