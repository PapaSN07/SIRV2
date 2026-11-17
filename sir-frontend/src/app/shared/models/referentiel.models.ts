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

export type StatutReferentiel = 'actifs' | 'inactifs' | 'tous';

export interface ReferentielListParams {
  page?: number;
  page_size?: number;
  type_reseau?: TypeReseau;
  statut?: StatutReferentiel;
  /** Recherche dans le code, le libellé et la description */
  q?: string;
  /** Colonne de tri (code, libelle, type_reseau, is_active), « - » devant = décroissant */
  tri?: string;
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
