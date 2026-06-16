export interface EquipementTransport {
  id: number;
  code: string;
  libelle: string;
  type_equipement: string;
  tension_kv: number | null;
  puissance_mva: number | null;
  is_active: boolean;
}

export interface EquipementTransportCreate {
  code: string;
  libelle: string;
  type_equipement: string;
  tension_kv?: number | null;
  puissance_mva?: number | null;
}

export interface EquipementTransportUpdate {
  code?: string;
  libelle?: string;
  type_equipement?: string;
  tension_kv?: number | null;
  puissance_mva?: number | null;
  is_active?: boolean;
}

export interface SourceTransportCreate {
  code: string;
  libelle: string;
  puissance_mw?: number | null;
}

export interface SourceTransportUpdate {
  code?: string;
  libelle?: string;
  puissance_mw?: number | null;
  is_active?: boolean;
}

export interface SourceTransport {
  id: number;
  code: string;
  libelle: string;
  puissance_mw: number | null;
  is_active: boolean;
}

export interface PosteLigne {
  id: number;
  poste_source_id: number;
  equipement_transport_id: number;
  is_active: boolean;
}

export interface ReseauTransportListParams {
  page?: number;
  page_size?: number;
  type_equipement?: string;
  equipement_transport_id?: number;
}
