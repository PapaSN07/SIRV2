export type TypeReseau = 'distribution' | 'transport' | 'commun';

export type ReferentielResource =
  | 'causes'
  | 'sieges'
  | 'signalisations'
  | 'natures'
  | 'types_end'
  | 'types_reseaux'
  | 'entreprises'
  | 'prestataires'
  | 'statuts'
  | 'direction_sources';

export interface ReferentielItem {
  id: number;
  code: string;
  libelle: string;
  type_reseau: TypeReseau | null;
  description: string | null;
  is_active: boolean;
}

export interface ReferentielListParams {
  page?: number;
  page_size?: number;
  type_reseau?: TypeReseau;
}

export interface ReferentielCreate {
  code: string;
  libelle: string;
  type_reseau?: TypeReseau | null;
  description?: string | null;
}

export interface ReferentielUpdate {
  code?: string;
  libelle?: string;
  type_reseau?: TypeReseau | null;
  description?: string | null;
  is_active?: boolean;
}
