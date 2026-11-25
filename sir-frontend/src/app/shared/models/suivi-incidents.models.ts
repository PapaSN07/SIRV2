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
