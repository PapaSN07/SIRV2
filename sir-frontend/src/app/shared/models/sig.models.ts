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


export interface CategorieSig {
  categorie: string;
  nombre: number;
}

export interface SyntheseSig {
  noeuds: number;
  noeuds_localises: number;
  noeuds_rattaches: number;
  troncons: number;
  longueur_km: number;
  feeders_sig: number;
  feeders_rattaches: number;
  stations: number;
  dernier_chargement: string | null;
  categories: CategorieSig[];
}

export interface StationSig {
  station: string;
  nom: string | null;
  delegation: string | null;
  region: string | null;
  noeuds: number;
  feeders: number;
  feeders_noms: string[];
  latitude: number | null;
  longitude: number | null;
  poste_source_sirv2: string | null;
}

export interface FeederSig {
  nom_feeder: string;
  troncons: number;
  longueur_km: number;
  tension_kv: number | null;
  noeuds: number;
  noeuds_localises: number;
  feeder_id: number | null;
  feeder_libelle: string | null;
  poste_source_libelle: string | null;
  date_chargement: string | null;
  code_sig: string | null;
  poste_source_sig: string | null;
  delegation: string | null;
  categorie_sig: string | null;
  km_sig: number | null;
  mise_en_service: string | null;
  attributs: Record<string, unknown> | null;
}

export interface TronconSigAdmin {
  id: number;
  nom_troncon: string | null;
  nom_feeder: string | null;
  feeder_id: number | null;
  nom_noeud_amont: string | null;
  code_noeud_amont: string | null;
  nom_noeud_aval: string | null;
  code_noeud_aval: string | null;
  tension_kv: number | null;
  longueur_m: number | null;
  date_chargement: string | null;
  imat_feeder: string | null;
  section: string | null;
  poste_source: string | null;
  type_conducteur: string | null;
  delegation: string | null;
  date_maj: string | null;
}

export interface NoeudSigAdmin {
  id: number;
  legacy_fid: number;
  nom: string | null;
  nom_feeder: string | null;
  feeder_id: number | null;
  station: string | null;
  categorie: string | null;
  coord_x: number | null;
  coord_y: number | null;
  latitude: number | null;
  longitude: number | null;
  delegation: string | null;
  region: string | null;
  puissance: string | null;
  famille_poste: string | null;
  cellule: string | null;
}

export interface SigListeParams {
  page?: number;
  page_size?: number;
  q?: string;
  tri?: string;
  nom_feeder?: string;
  station?: string;
  categorie?: string;
  localisation?: 'localise' | 'non_localise';
  rattachement?: 'rattache' | 'non_rattache';
}

export interface Defauts100KmLigne {
  libelle: string;
  detail: string | null;
  defauts: number;
  permanents: number;
  longueur_km: number;
  defauts_100km: number | null;
  permanents_100km: number | null;
}

export interface Defauts100KmNature {
  nature: string;
  defauts: number;
  defauts_100km: number | null;
}

export interface Defauts100Km {
  debut: string;
  fin: string;
  global: Defauts100KmLigne;
  par_nature: Defauts100KmNature[];
  par_service: Defauts100KmLigne[];
  par_feeder: Defauts100KmLigne[];
  defauts_sans_longueur: number;
}
