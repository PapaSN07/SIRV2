import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, forkJoin, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import {
  CategorieFis,
  CorrespondanceFis,
  CorrespondanceFisCreate,
} from '../../../shared/models/correspondance-fis.models';
import { ReferentielItem, ReferentielResource } from '../../../shared/models/referentiel.models';
import { ReferentielService } from './referentiel.service';

const RESSOURCES: Record<CategorieFis, ReferentielResource> = {
  nature: 'natures',
  cause: 'causes',
  siege: 'sieges',
  signalisation: 'signalisations',
};

/** Correspondances FIS : lecture (écran d'import), création et suppression (Admin SCR). */
@Injectable({ providedIn: 'root' })
export class CorrespondanceFisService {
  private readonly http = inject(HttpClient);
  private readonly referentiel = inject(ReferentielService);
  private readonly apiUrl = `${environment.apiUrl}/correspondances-fis`;

  lister(categorie: CategorieFis | null = null): Observable<CorrespondanceFis[]> {
    let params = new HttpParams();
    if (categorie) params = params.set('categorie', categorie);
    return this.http
      .get<ApiResponse<CorrespondanceFis[]>>(this.apiUrl, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  creer(body: CorrespondanceFisCreate): Observable<CorrespondanceFis> {
    return this.http
      .post<ApiResponse<CorrespondanceFis>>(this.apiUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  supprimer(id: number): Observable<void> {
    return this.http.delete<ApiResponse<null>>(`${this.apiUrl}/${id}`).pipe(
      map((res) => {
        if (res.status === 'error') throw new Error(res.error ?? 'Erreur API');
      }),
    );
  }

  /**
   * Cibles possibles d'une correspondance : entrées actives du Référentiel, de type
   * distribution ou commun (natures : toutes les actives, elles n'ont pas de type réseau).
   */
  rechercherCibles(categorie: CategorieFis, q: string): Observable<ReferentielItem[]> {
    const ressource = RESSOURCES[categorie];
    const base = { page: 1, page_size: 50, statut: 'actifs' as const, q, tri: 'libelle' };
    if (categorie === 'nature') {
      return this.referentiel.list(ressource, base).pipe(map((res) => res.items));
    }
    return forkJoin([
      this.referentiel.list(ressource, { ...base, type_reseau: 'distribution' }),
      this.referentiel.list(ressource, { ...base, type_reseau: 'commun' }),
    ]).pipe(
      map(([distribution, commun]) =>
        [...distribution.items, ...commun.items]
          .filter((item) => item.is_active)
          .sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr')),
      ),
    );
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
