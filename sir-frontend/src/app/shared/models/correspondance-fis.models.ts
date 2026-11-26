/**
 * Correspondances FIS administrées (Admin SCR) : libellé du fichier FIS → entrée du Référentiel.
 * Miroir de `sir-backend/app/schemas/correspondance_fis.py`.
 */

export type CategorieFis = 'nature' | 'cause' | 'siege' | 'signalisation';

export interface CorrespondanceFis {
  id: number;
  categorie: CategorieFis;
  /** Libellé normalisé par l'API (minuscules, espaces de bord retirés). */
  libelle_fis: string;
  referentiel_id: number;
  referentiel_code: string;
  referentiel_libelle: string;
  /** Cause seulement : null = règle de l'import. */
  is_force_majeure: boolean | null;
  created_at: string | null;
}

export interface CorrespondanceFisCreate {
  categorie: CategorieFis;
  libelle_fis: string;
  referentiel_id: number;
  /** Cause seulement ; null ou absent = règle de l'import. */
  is_force_majeure?: boolean | null;
}

export const CATEGORIES_FIS: readonly { key: CategorieFis; label: string }[] = [
  { key: 'nature', label: 'Nature' },
  { key: 'cause', label: 'Cause' },
  { key: 'siege', label: 'Siège' },
  { key: 'signalisation', label: 'Signalisation' },
];

export function libelleCategorieFis(categorie: CategorieFis): string {
  return CATEGORIES_FIS.find((c) => c.key === categorie)?.label ?? categorie;
}
