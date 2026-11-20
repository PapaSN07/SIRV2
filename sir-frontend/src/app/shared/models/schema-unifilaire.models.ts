/** Schéma unifilaire importé (PDF AutoCAD) : dimensions en points PDF. */
export interface SchemaUnifilaire {
  id: number;
  nom: string;
  fichier: string;
  region_id: number | null;
  region_libelle: string | null;
  largeur: number;
  hauteur: number;
  zoom_max: number;
  nb_postes: number;
  importe_le: string;
}

/** Poste cliquable du schéma : symbole et libellé (points PDF, origine en haut à gauche). */
export interface PosteSchema {
  id: number;
  rang: number;
  libelle: string | null;
  forme: 'carre' | 'rond' | string;
  puissance_kva: number | null;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  lx0: number | null;
  ly0: number | null;
  lx1: number | null;
  ly1: number | null;
  poste_id: number | null;
  poste_code: string | null;
  poste_libelle: string | null;
  /** auto (même nom), manuel (choisi par l'Admin SCR), ambigu (plusieurs postes SIRV2 de ce nom) */
  rapprochement: 'auto' | 'manuel' | 'ambigu' | null;
}

export interface DerivationSchema {
  depuis_id: number | null;
  postes: PosteSchema[];
}

/** Postes entre deux postes : le long de la ligne, en antenne, dérivations à choisir. */
export interface PostesEntre {
  chemin: PosteSchema[];
  antennes: PosteSchema[];
  derivations: DerivationSchema[];
  postes_hors_limite: number;
  trace: [number, number][];
}
