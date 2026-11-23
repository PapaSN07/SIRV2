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

// ── Rapprochement Schéma / SIG / SIR ────────────────────────────────────────────

export interface NoeudSigCourt {
  id: number;
  nom: string | null;
  nom_feeder: string | null;
  station: string | null;
  categorie: string | null;
}

export interface PosteSirCourt {
  id: number;
  code: string;
  libelle: string;
  feeder_libelle: string | null;
  poste_source_libelle: string | null;
}

/** Un poste du schéma, son nœud SIG et son poste SIR (ou la décision SIR). */
export interface LigneRapprochement {
  id: number;
  rang: number;
  libelle: string | null;
  sig: NoeudSigCourt | null;
  rapprochement_sig: 'auto' | 'manuel' | 'ambigu' | null;
  sir: PosteSirCourt | null;
  rapprochement: 'auto' | 'manuel' | 'ambigu' | null;
  /** inactif (hors service, non repris dans SIR) ou a_creer (création proposée) */
  statut_sir: 'inactif' | 'a_creer' | null;
  demande_id: number | null;
}

export type FiltreRapprochement = 'tous' | 'a_traiter' | 'sig_manquant' | 'sir_relies' | 'ambigus' | 'a_creer' | 'inactifs';

export interface CompteursRapprochement {
  total: number;
  sans_nom: number;
  sig_relies: number;
  sig_ambigus: number;
  sir_relies: number;
  sir_ambigus: number;
  a_creer: number;
  inactifs: number;
  a_traiter: number;
}

export interface RapprochementSig {
  relies: number;
  ambigus: number;
  non_trouves: number;
}

/** Pré-remplissage de la recherche assistée (poste source, feeder, poste). */
export interface SuggestionCreation {
  libelle: string;
  poste_source_id: number | null;
  poste_source_libelle: string | null;
  feeder_id: number | null;
  feeder_libelle: string | null;
  origine: 'sig' | 'voisins' | null;
}

export type StatutPosteACreer = 'propose' | 'valide' | 'rejete';

export interface PosteACreer {
  id: number;
  schema_nom: string | null;
  libelle_schema: string | null;
  libelle: string;
  poste_source_id: number;
  poste_source_libelle: string | null;
  feeder_id: number;
  feeder_libelle: string | null;
  noeud_sig_nom: string | null;
  statut: StatutPosteACreer;
  motif_rejet: string | null;
  poste_id: number | null;
  poste_code: string | null;
  propose_par: string | null;
  propose_le: string;
  traite_par: string | null;
  traite_le: string | null;
}
