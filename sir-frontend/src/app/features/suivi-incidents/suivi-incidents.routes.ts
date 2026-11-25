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
    loadComponent: () => import('./vue-ensemble/vue-ensemble.component').then((m) => m.VueEnsembleComponent),
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
    loadComponent: () => import('./evolution/evolution.component').then((m) => m.EvolutionComponent),
  },
  {
    path: 'reseau',
    title: 'Réseau — Suivi incidents',
    loadComponent: () => import('./reseau/reseau.component').then((m) => m.ReseauComponent),
  },
  {
    path: 'saifi-saidi',
    title: 'SAIFI / SAIDI — Suivi incidents',
    loadComponent: () => import('./saifi-saidi/saifi-saidi.component').then((m) => m.SaifiSaidiComponent),
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
