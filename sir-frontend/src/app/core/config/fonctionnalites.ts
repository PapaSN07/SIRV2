import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

/**
 * Parties de l'application affichées ou non.
 *
 * transport : interruptions transport / OMVG, réseau transport, rapports transport.
 * Masqué le 06/11/2026 (reprise SIR v1 du transport en attente) ; repasser à true pour le
 * réafficher. Le HTB reste visible dans la synthèse SAIFI / SAIDI de l'accueil.
 */
export const FONCTIONNALITES = {
  transport: false,
  /**
   * Menu « Suivi incidents » (fusion du tableau de bord Suivi incidents SIR).
   * Visible depuis le 26/11/2026 ; repasser à false pour le masquer (l'aperçu par
   * `localStorage['sir_apercu']` contenant « suivi-incidents » reste alors possible).
   */
  suiviIncidents: true,
} as const;

/** Route d'une partie masquée : retour à l'accueil. */
export const transportActifGuard: CanActivateFn = () =>
  FONCTIONNALITES.transport ? true : inject(Router).createUrlTree(['/']);

/** Menu Suivi incidents affiché : activé, ou aperçu demandé sur ce poste. */
export function suiviIncidentsActif(): boolean {
  if (FONCTIONNALITES.suiviIncidents) return true;
  try {
    return (localStorage.getItem('sir_apercu') ?? '').split(',').includes('suivi-incidents');
  } catch {
    return false;
  }
}

export const suiviIncidentsActifGuard: CanActivateFn = () =>
  suiviIncidentsActif() ? true : inject(Router).createUrlTree(['/']);
