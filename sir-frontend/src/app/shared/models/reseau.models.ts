export interface Feeder {
  id: number;
  code: string;
  libelle: string;
  poste_source_id: number;
  service_id: number | null;
  tension_kv: number | null;
  puissance_installee_mva: number | null;
  is_active: boolean;
}

export interface FeederCreate {
  code: string;
  libelle: string;
  poste_source_id: number;
  service_id?: number | null;
  tension_kv?: number | null;
  puissance_installee_mva?: number | null;
}

export interface FeederUpdate {
  code?: string;
  libelle?: string;
  poste_source_id?: number;
  service_id?: number | null;
  tension_kv?: number | null;
  puissance_installee_mva?: number | null;
  is_active?: boolean;
}

export interface PosteSource {
  id: number;
  code: string;
  libelle: string;
  region_id: number | null;
  puissance_mva: number | null;
  is_active: boolean;
}

export interface PosteSourceCreate {
  code: string;
  libelle: string;
  region_id?: number | null;
  puissance_mva?: number | null;
}

export interface PosteSourceUpdate {
  code?: string;
  libelle?: string;
  region_id?: number | null;
  puissance_mva?: number | null;
  is_active?: boolean;
}

export interface Poste {
  id: number;
  code: string;
  libelle: string;
  feeder_id: number | null;
  service_id: number | null;
  puissance_kva: number | null;
  nombre_clients: number | null;
  is_active: boolean;
}

export interface PosteCreate {
  code: string;
  libelle: string;
  feeder_id?: number | null;
  service_id?: number | null;
  puissance_kva?: number | null;
  nombre_clients?: number | null;
}

export interface PosteUpdate {
  code?: string;
  libelle?: string;
  feeder_id?: number | null;
  service_id?: number | null;
  puissance_kva?: number | null;
  nombre_clients?: number | null;
  is_active?: boolean;
}

export interface ReseauListParams {
  page?: number;
  page_size?: number;
  feeder_id?: number;
  service_id?: number;
  region_id?: number;
}
