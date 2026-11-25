import { Routes } from '@angular/router';
import { OngletAVenir } from './onglet-a-venir/onglet-a-venir.component';

const aVenir = (ongletAVenir: OngletAVenir) => ({
  loadComponent: () =>
    import('./onglet-a-venir/onglet-a-venir.component').then((m) => m.OngletAVenirComponent),
  data: { ongletAVenir },
});

/** Onglets du menu Suivi incidents (docs/fusion_suivi_incidents.md §2 et §7). */
export const SUIVI_INCIDENTS_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'vue-ensemble' },
  {
    path: 'vue-ensemble',
    title: 'Vue d’ensemble — Suivi incidents',
    ...aVenir({
      titre: 'Vue d’ensemble',
      etape: 3,
      contenu: [
        'Indicateurs clés de la période, avec l’écart par rapport à la période précédente',
        'Répartition Travaux / Incident / Délestage (nombre et durée)',
        'Énergie non distribuée HTA, HTB et totale',
        'Classement par région, service, poste source et feeder ; un clic filtre les autres onglets',
      ],
    }),
  },
  {
    path: 'carte',
    title: 'Carte — Suivi incidents',
    ...aVenir({
      titre: 'Carte',
      etape: 6,
      contenu: [
        'Postes touchés sur la carte (taille = nombre d’interruptions, couleur = nature)',
        'Mode SAIFI / SAIDI : contribution des services et des postes',
        'Un clic sur un poste filtre les autres onglets',
      ],
    }),
  },
  {
    path: 'evolution',
    title: 'Évolution — Suivi incidents',
    ...aVenir({
      titre: 'Évolution',
      etape: 4,
      contenu: [
        'Nombre et durée des interruptions par jour, par semaine Senelec ou par mois selon la période',
        'Répartition par nature',
      ],
    }),
  },
  {
    path: 'reseau',
    title: 'Réseau — Suivi incidents',
    ...aVenir({
      titre: 'Réseau',
      etape: 4,
      contenu: [
        'Postes sources et feeders les plus touchés : tableaux triables avec recherche',
        'Nombre, durée, END et contribution au SAIFI',
        'Export Excel',
      ],
    }),
  },
  {
    path: 'saifi-saidi',
    title: 'SAIFI / SAIDI — Suivi incidents',
    ...aVenir({
      titre: 'SAIFI / SAIDI',
      etape: 5,
      contenu: [
        'Synthèse HTA / HTB / total : semaine passée, mois en cours, cumul annuel',
        'Évolution mensuelle et cumul depuis janvier',
        'Rapport par nature, tableau mois × nature, contribution par service',
      ],
    }),
  },
  {
    path: 'localisation',
    title: 'Localisation — Suivi incidents',
    ...aVenir({
      titre: 'Localisation',
      etape: 6,
      contenu: [
        'Part des postes touchés localisés sur la carte SIG',
        'Postes non localisés par poste source, avec un lien vers leur correction',
      ],
    }),
  },
];
