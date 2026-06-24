export interface TronconSig {
  id: number;
  legacy_id: number;
  legacy_fid: number | null;
  nom_feeder: string | null;
  feeder_id: number | null;
  nom_troncon: string | null;
  nom_noeud_amont: string | null;
  code_noeud_amont: string | null;
  nom_noeud_aval: string | null;
  code_noeud_aval: string | null;
  tension_kv: number | null;
  longueur_m: number | null;
  date_chargement: string | null;
}

export interface TronconSigChaine {
  troncon: TronconSig;
  chaine_aval: TronconSig[];
}

export interface SigListParams {
  feeder_id: number;
  page?: number;
  page_size?: number;
  search?: string;
}
