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
} as const;

/** Route d'une partie masquée : retour à l'accueil. */
export const transportActifGuard: CanActivateFn = () =>
  FONCTIONNALITES.transport ? true : inject(Router).createUrlTree(['/']);
