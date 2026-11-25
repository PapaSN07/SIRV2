/**
 * Semaine d'exploitation SENELEC : du samedi au vendredi, numérotée par la semaine ISO de
 * son vendredi (S43 2026 = samedi 17/10 → vendredi 23/10). Même règle que le backend
 * (`app/services/periodes.py`) et le rapport hebdo DD.
 *
 * Les dates sont des chaînes « AAAA-MM-JJ » : pas de fuseau horaire en jeu.
 */

export interface SemaineSenelec {
  numero: number;
  annee: number;
  /** Samedi, « AAAA-MM-JJ ». */
  debut: string;
  /** Vendredi, « AAAA-MM-JJ ». */
  fin: string;
}

const JOUR_MS = 86_400_000;

function versDate(iso: string): Date {
  const [a, m, j] = iso.split('-').map(Number);
  return new Date(Date.UTC(a, m - 1, j));
}

export function versIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function ajouterJours(iso: string, jours: number): string {
  return versIso(new Date(versDate(iso).getTime() + jours * JOUR_MS));
}

/** Aujourd'hui en heure locale, « AAAA-MM-JJ ». */
export function aujourdhuiIso(): string {
  const d = new Date();
  return versIso(new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())));
}

/** Semaine ISO (numéro, année) d'une date. */
function semaineIso(d: Date): { numero: number; annee: number } {
  // Le jeudi de la même semaine (lundi → dimanche) porte l'année ISO.
  const jeudi = new Date(d.getTime() + (3 - ((d.getUTCDay() + 6) % 7)) * JOUR_MS);
  const annee = jeudi.getUTCFullYear();
  const premierJanvier = Date.UTC(annee, 0, 1);
  const numero = 1 + Math.floor((jeudi.getTime() - premierJanvier) / (7 * JOUR_MS));
  return { numero, annee };
}

/** Semaine Senelec qui contient `jour`. */
export function semaineSenelec(jour: string): SemaineSenelec {
  const d = versDate(jour);
  const versVendredi = (5 - d.getUTCDay() + 7) % 7; // vendredi = 5
  const vendredi = new Date(d.getTime() + versVendredi * JOUR_MS);
  const { numero, annee } = semaineIso(vendredi);
  return { numero, annee, debut: versIso(new Date(vendredi.getTime() - 6 * JOUR_MS)), fin: versIso(vendredi) };
}

/** Dernière semaine terminée : son vendredi est strictement avant `aujourdhui`. */
export function semaineSenelecPassee(aujourdhui: string): SemaineSenelec {
  return semaineSenelec(ajouterJours(semaineSenelec(aujourdhui).debut, -1));
}

/** « S47 · 14/11 → 20/11/2026 ». */
export function libelleSemaine(s: SemaineSenelec): string {
  return `S${s.numero} · ${jourMois(s.debut)} → ${dateCourte(s.fin)}`;
}

/** « 14/11 ». */
export function jourMois(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/** « 20/11/2026 ». */
export function dateCourte(iso: string): string {
  return `${jourMois(iso)}/${iso.slice(0, 4)}`;
}
