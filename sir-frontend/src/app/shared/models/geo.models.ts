export interface Region {
  id: number;
  code: string;
  libelle: string;
  is_active: boolean;
}

export interface Delegation {
  id: number;
  region_id: number;
  code: string;
  libelle: string;
  is_active: boolean;
}

export interface Agence {
  id: number;
  delegation_id: number;
  code: string;
  libelle: string;
  is_active: boolean;
}

export interface Service {
  id: number;
  agence_id: number;
  code: string;
  libelle: string;
  is_active: boolean;
}
