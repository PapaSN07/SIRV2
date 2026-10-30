import { EMPTY, Observable, expand, map, reduce } from 'rxjs';
import { PaginatedResponse } from '../models/api.models';

/** Taille de page maximale acceptée par l'API (`page_size` ≤ 100). */
export const PAGE_SIZE_MAX = 100;

/**
 * Charge toutes les pages d'une liste paginée (100 éléments par appel) et renvoie
 * l'ensemble des éléments. `maxPages` évite une boucle sans fin si `total` est faux.
 */
export function toutesLesPages<T>(
  charger: (page: number, pageSize: number) => Observable<PaginatedResponse<T>>,
  maxPages = 50,
): Observable<T[]> {
  return charger(1, PAGE_SIZE_MAX).pipe(
    expand((res) =>
      res.page * res.page_size < res.total && res.page < maxPages && res.items.length > 0
        ? charger(res.page + 1, PAGE_SIZE_MAX)
        : EMPTY,
    ),
    map((res) => res.items),
    reduce((tous: T[], items: T[]) => tous.concat(items), []),
  );
}
