import { Routes } from '@angular/router';
/** Onglets du menu Suivi incidents (docs/fusion_suivi_incidents.md §2, §8 à §11). */
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
    loadComponent: () => import('./carte/carte.component').then((m) => m.CarteComponent),
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
    loadComponent: () => import('./localisation/localisation.component').then((m) => m.LocalisationComponent),
  },
];
