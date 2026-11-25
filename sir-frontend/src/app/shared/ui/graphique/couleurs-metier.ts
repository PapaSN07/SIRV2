/**
 * Couleurs métier des graphiques — miroir des jetons `$nature-*` / `$reseau-*` de
 * `styles/_sir-tokens.scss` (ECharts dessine sur un canvas : il lui faut des valeurs, pas des
 * variables SCSS).
 */
export const COULEURS = {
  navy: '#262051',
  violet: '#5b2a9e',
  magenta: '#e6007e',
  orange: '#f58220',
  rouge: '#e63329',
  ambre: '#fdb913',
  texte: '#1a1626',
  texteSecondaire: '#6b6580',
  grille: '#ede9f5',
} as const;

/** Catégories de nature (rapport hebdo DD). */
export const COULEUR_NATURE: Record<string, string> = {
  travaux: COULEURS.navy,
  incident: COULEURS.orange,
  delestage: COULEURS.rouge,
  autre: COULEURS.texteSecondaire,
};

export const COULEUR_RESEAU = { hta: COULEURS.violet, htb: COULEURS.magenta } as const;

/** Suite par défaut quand les séries n'ont pas de couleur métier. */
export const PALETTE = [COULEURS.violet, COULEURS.orange, COULEURS.navy, COULEURS.magenta, COULEURS.ambre, COULEURS.rouge];
