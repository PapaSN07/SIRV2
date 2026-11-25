import { Signal } from '@angular/core';
import { toObservable } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, distinctUntilChanged, filter, map, of, switchMap, tap } from 'rxjs';
import { FiltresIncidents } from '../../../shared/models/suivi-incidents.models';

/** État d'un bloc de données d'un onglet. */
export type Etat<T> = { type: 'chargement' } | { type: 'erreur'; message: string } | { type: 'ok'; donnees: T };

export const memes = <T>(a: T, b: T): boolean => JSON.stringify(a) === JSON.stringify(b);

/** Message en français pour un bloc en erreur (jamais de message technique). */
export function messageErreur(err: unknown): string {
  if (err instanceof HttpErrorResponse && err.status === 403) {
    return 'Ces données sont hors de votre périmètre.';
  }
  if (err instanceof HttpErrorResponse && (err.status === 0 || err.status >= 500)) {
    return 'Les indicateurs n’ont pas pu être chargés (serveur indisponible). Réessayez dans un instant.';
  }
  const m = (err as { message?: unknown } | null)?.message;
  return typeof m === 'string' && m ? m : 'Les données n’ont pas pu être chargées.';
}

/** Charge une ressource à chaque nouvelle clé ; chaque état est remis à `cible`. */
export function charger<K, T>(
  cle$: Observable<K>,
  appel: (cle: K) => Observable<T>,
  cible: (e: Etat<T>) => void,
): Observable<unknown> {
  return cle$.pipe(
    tap(() => cible({ type: 'chargement' })),
    switchMap((cle) =>
      appel(cle).pipe(
        map((donnees) => cible({ type: 'ok', donnees })),
        catchError((err: unknown) => of(cible({ type: 'erreur', message: messageErreur(err) }))),
      ),
    ),
  );
}

/** Filtres résolus par l'API (périmètre imposé compris), émis seulement quand ils changent. */
export function filtresResolus$(resolus: Signal<FiltresIncidents | null>): Observable<FiltresIncidents> {
  return toObservable(resolus).pipe(
    filter((x): x is FiltresIncidents => x !== null),
    distinctUntilChanged<FiltresIncidents>(memes),
  );
}
