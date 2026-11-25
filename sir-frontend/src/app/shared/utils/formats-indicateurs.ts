/**
 * Formats uniques des indicateurs (locale fr-FR), pour que la même grandeur s'écrive
 * partout de la même façon : SAIFI 3 décimales, SAIDI en heures 3 décimales (comme l'accueil),
 * END en MWh
 * 1 décimale (kWh sous 1 MWh), durées « 12 h 30 », pourcentages « 84,5 % ».
 */

const nombre = (min: number, max: number) =>
  new Intl.NumberFormat('fr-FR', { minimumFractionDigits: min, maximumFractionDigits: max });

const ENTIER = nombre(0, 0);
const UNE = nombre(1, 1);
const TROIS = nombre(3, 3);

const TIRET = '—';
/** Espace fine insécable avant « % » : le symbole ne passe jamais seul à la ligne. */
const ESPACE_FINE = ' ';

function absent(v: number | null | undefined): v is null | undefined {
  return v === null || v === undefined || Number.isNaN(v);
}

/** Nombre entier avec séparateur de milliers (« 12 345 »). */
export function formatEntier(v: number | null | undefined): string {
  return absent(v) ? TIRET : ENTIER.format(v);
}

/** SAIFI : nombre moyen de coupures par client, 3 décimales (contributions faibles lisibles). */
export function formatSaifi(v: number | null | undefined): string {
  return absent(v) ? TIRET : TROIS.format(v);
}

/** SAIDI en heures, 3 décimales (« 0,325 h ») ; détail « h mn » : formatDuree. */
export function formatSaidi(heures: number | null | undefined): string {
  return absent(heures) ? TIRET : `${TROIS.format(heures)} h`;
}

/** Détail d'une durée en heures : « 5 h 21 » (pour les infobulles). */
export function formatDuree(heures: number | null | undefined): string {
  if (absent(heures)) return TIRET;
  const totalMinutes = Math.round(heures * 60);
  const h = Math.floor(totalMinutes / 60);
  const mn = totalMinutes % 60;
  if (h === 0) return `${mn} mn`;
  return `${ENTIER.format(h)} h ${String(mn).padStart(2, '0')}`;
}

/** END : MWh avec 1 décimale, kWh entiers sous 1 MWh. */
export function formatEnd(mwh: number | null | undefined): string {
  if (absent(mwh)) return TIRET;
  if (Math.abs(mwh) < 1) return `${ENTIER.format(mwh * 1000)} kWh`;
  return `${UNE.format(mwh)} MWh`;
}

/** END en deux parties pour une carte KPI (unité affichée plus petite) : « 1 843,3 » + « MWh ». */
export function formatEndParties(mwh: number | null | undefined): { valeur: string; unite: string | null } {
  if (absent(mwh)) return { valeur: TIRET, unite: null };
  if (Math.abs(mwh) < 1) return { valeur: ENTIER.format(mwh * 1000), unite: 'kWh' };
  return { valeur: UNE.format(mwh), unite: 'MWh' };
}

/** Pourcentage à partir d'une part (0,845 → « 84,5 % »). */
export function formatPart(part: number | null | undefined): string {
  return absent(part) ? TIRET : `${UNE.format(part * 100)}${ESPACE_FINE}%`;
}

/**
 * Écart relatif entre deux périodes (« +12,0 % »), ou null si la période de comparaison
 * est vide (pas de division par zéro).
 */
export function ecartRelatif(actuel: number | null | undefined, precedent: number | null | undefined): number | null {
  if (absent(actuel) || absent(precedent) || precedent === 0) return null;
  return (actuel - precedent) / Math.abs(precedent);
}

export function formatEcart(ecart: number | null): string {
  if (ecart === null) return TIRET;
  const signe = ecart > 0 ? '+' : ecart < 0 ? '−' : '';
  // Au-delà de ±999 %, la valeur exacte n'aide pas la lecture (période de comparaison presque vide)
  if (Math.abs(ecart) > 9.99) return `> ${signe}999${ESPACE_FINE}%`;
  return `${signe}${UNE.format(Math.abs(ecart) * 100)}${ESPACE_FINE}%`;
}
