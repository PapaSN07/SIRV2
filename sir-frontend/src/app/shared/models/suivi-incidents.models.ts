/**
 * Menu « Suivi incidents » : filtres communs aux onglets.
 * Miroir des schémas Pydantic `app/schemas/suivi_incidents.py` (FiltresIncidents, FiltresResolus).
 */

export type ReseauCause = 'hta' | 'htb';

/** Filtres envoyés à l'API (dates « AAAA-MM-JJ », fin incluse). */
export interface FiltresIncidents {
  debut: string;
  fin: string;
  region_id: number | null;
  service_id: number | null;
  poste_source_id: number | null;
  feeder_id: number | null;
  nature_id: number | null;
  cause_id: number | null;
  reseau: ReseauCause | null;
  exogene: boolean | null;
}

export interface SemaineSenelecApi {
  numero: number;
  annee: number;
  debut: string;
  fin: string;
}

export type NiveauPerimetre = 'national' | 'region' | 'service';

export interface PerimetreSuivi {
  niveau: NiveauPerimetre;
  scope_id: number | null;
  region_verrouillee: boolean;
  service_verrouille: boolean;
}

/** Réponse de GET /suivi-incidents/filtres : filtres complétés et périmètre de l'utilisateur. */
export interface FiltresResolus {
  filtres: FiltresIncidents;
  semaine: SemaineSenelecApi | null;
  libelle_periode: string;
  perimetre: PerimetreSuivi;
}

/** Raccourcis du sélecteur de période. */
export type ModePeriode = 'semaine' | 'mois' | 'annee' | 'personnalise';

/* ── Onglet Vue d'ensemble (GET /suivi-incidents/vue-ensemble, /classement) ── */

export interface PeriodeSuivi {
  debut: string;
  fin: string;
  libelle: string;
}

export interface KpiSuivi {
  nombre_interruptions: number;
  duree_totale_heures: number;
  duree_moyenne_minutes: number | null;
  postes_touches: number;
  coupures_clients: number;
  end_mwh: number;
}

export type CategorieNature = 'incident' | 'delestage' | 'travaux' | 'autre';

export interface RepartitionNature {
  categorie: CategorieNature;
  libelle: string;
  nombre: number;
  duree_heures: number;
  end_mwh: number;
  part: number;
}

export interface RepartitionReseau {
  reseau: ReseauCause | 'total';
  nombre: number;
  duree_heures: number;
  end_mwh: number;
}

export interface VueEnsemble {
  filtres: FiltresResolus;
  periode_precedente: PeriodeSuivi;
  kpi: KpiSuivi;
  kpi_precedent: KpiSuivi;
  natures: RepartitionNature[];
  reseaux: RepartitionReseau[];
}

export type NiveauClassement = 'service' | 'poste_source' | 'feeder';

export interface LigneClassement {
  id: number | null;
  code: string | null;
  libelle: string;
  nombre: number;
  duree_heures: number;
  end_mwh: number;
  part: number;
}

export interface ClassementSuivi {
  niveau: NiveauClassement;
  total_interruptions: number;
  lignes: LigneClassement[];
  autres: LigneClassement | null;
}

/* ── Onglets Évolution et Réseau (GET /suivi-incidents/evolution, /reseau) ── */

export type Granularite = 'jour' | 'semaine' | 'mois';

export interface PointEvolution {
  debut: string;
  fin: string;
  libelle: string;
  nombre: number;
  duree_heures: number;
  end_mwh: number;
  natures: Record<CategorieNature, number>;
}

export interface EvolutionSuivi {
  granularite: Granularite;
  points: PointEvolution[];
}

export type NiveauReseau = 'poste_source' | 'feeder';

export interface LigneReseau {
  id: number | null;
  code: string | null;
  libelle: string;
  poste_source: string | null;
  nombre: number;
  duree_heures: number;
  end_mwh: number;
  coupures_clients: number;
  postes_touches: number;
  part: number;
}

export interface ReseauSuivi {
  niveau: NiveauReseau;
  total_interruptions: number;
  lignes: LigneReseau[];
}

