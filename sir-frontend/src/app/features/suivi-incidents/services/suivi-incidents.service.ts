import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SANS_REDIRECTION_403 } from '../../../core/auth/error.interceptor';
import { ApiResponse } from '../../../shared/models/api.models';
import { FiltresIncidents, FiltresResolus } from '../../../shared/models/suivi-incidents.models';

/** Appels HTTP du menu « Suivi incidents » (`/api/v1/suivi-incidents`). */
@Injectable({ providedIn: 'root' })
export class SuiviIncidentsService {
  private readonly apiUrl = `${environment.apiUrl}/suivi-incidents`;

  constructor(private readonly http: HttpClient) {}

  /**
   * Filtres complétés (période par défaut, périmètre imposé par le rôle) et libellé de période.
   * Un 403 (région ou service hors périmètre, ex. lien partagé) est traité par l'appelant.
   */
  getFiltres(filtres: Partial<FiltresIncidents>): Observable<FiltresResolus> {
    return this.http
      .get<ApiResponse<FiltresResolus>>(`${this.apiUrl}/filtres`, {
        params: parametresFiltres(filtres),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }
}

/** Paramètres de requête des filtres : seules les valeurs renseignées partent. */
export function parametresFiltres(filtres: Partial<FiltresIncidents>): HttpParams {
  let params = new HttpParams();
  for (const [cle, valeur] of Object.entries(filtres)) {
    if (valeur === null || valeur === undefined || valeur === '') continue;
    params = params.set(cle, String(valeur));
  }
  return params;
}

function unwrap<T>(res: ApiResponse<T>): T {
  if (res.status !== 'success' || res.data === null) {
    throw new Error(res.error ?? 'Réponse inattendue du serveur');
  }
  return res.data;
}
