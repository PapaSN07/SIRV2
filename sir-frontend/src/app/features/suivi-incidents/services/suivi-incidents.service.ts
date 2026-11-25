import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, catchError, from, map, switchMap, throwError } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { SANS_REDIRECTION_403 } from '../../../core/auth/error.interceptor';
import { ApiResponse } from '../../../shared/models/api.models';
import {
  ClassementSuivi,
  EvolutionSuivi,
  FiltresIncidents,
  FiltresResolus,
  Granularite,
  NiveauClassement,
  NiveauReseau,
  ReseauSuivi,
  SaifiSaidiSuivi,
  VueEnsemble,
} from '../../../shared/models/suivi-incidents.models';

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

  /** Indicateurs de la période et de la période précédente, natures, réseaux HTA / HTB. */
  getVueEnsemble(filtres: FiltresIncidents): Observable<VueEnsemble> {
    return this.http
      .get<ApiResponse<VueEnsemble>>(`${this.apiUrl}/vue-ensemble`, {
        params: parametresFiltres(filtres),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }

  /** Classement des services, postes sources ou feeders les plus touchés. */
  getClassement(filtres: FiltresIncidents, niveau: NiveauClassement, limite = 10): Observable<ClassementSuivi> {
    return this.http
      .get<ApiResponse<ClassementSuivi>>(`${this.apiUrl}/classement`, {
        params: parametresFiltres(filtres).set('niveau', niveau).set('limite', limite),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }

  /** Série d'interruptions par jour, semaine Senelec ou mois (« auto » : selon la durée de la période). */
  getEvolution(filtres: FiltresIncidents, granularite: Granularite | 'auto' = 'auto'): Observable<EvolutionSuivi> {
    return this.http
      .get<ApiResponse<EvolutionSuivi>>(`${this.apiUrl}/evolution`, {
        params: parametresFiltres(filtres).set('granularite', granularite),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }

  /** SAIFI / SAIDI du périmètre (contribution des interruptions filtrées), par réseau, nature, mois, service. */
  getSaifiSaidi(filtres: FiltresIncidents): Observable<SaifiSaidiSuivi> {
    return this.http
      .get<ApiResponse<SaifiSaidiSuivi>>(`${this.apiUrl}/saifi-saidi`, {
        params: parametresFiltres(filtres),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }

  /** Tous les postes sources ou feeders touchés (tri, recherche et pages côté écran). */
  getReseau(filtres: FiltresIncidents, niveau: NiveauReseau): Observable<ReseauSuivi> {
    return this.http
      .get<ApiResponse<ReseauSuivi>>(`${this.apiUrl}/reseau`, {
        params: parametresFiltres(filtres).set('niveau', niveau),
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(map((res) => unwrap(res)));
  }

  /** Fichier Excel du tableau Réseau ; une erreur reçue en Blob est relue pour garder le message. */
  exporterReseau(filtres: FiltresIncidents, niveau: NiveauReseau): Observable<{ blob: Blob; nom: string }> {
    return this.http
      .get(`${this.apiUrl}/reseau/export`, {
        params: parametresFiltres(filtres).set('niveau', niveau),
        responseType: 'blob',
        observe: 'response',
        context: new HttpContext().set(SANS_REDIRECTION_403, true),
      })
      .pipe(
        map((res) => {
          const disposition = res.headers.get('Content-Disposition') ?? '';
          const nom = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `suivi_${niveau}.xlsx`;
          return { blob: res.body ?? new Blob(), nom };
        }),
        catchError((err: HttpErrorResponse) => {
          if (!(err.error instanceof Blob)) return throwError(() => err);
          return from(err.error.text()).pipe(
            switchMap((texte) => {
              let message = 'L’export n’a pas pu être produit.';
              try {
                const corps = JSON.parse(texte) as { error?: string; detail?: { error?: string } };
                message = corps.error ?? corps.detail?.error ?? message;
              } catch {
                /* corps non JSON : message par défaut */
              }
              return throwError(() => new Error(message));
            }),
          );
        }),
      );
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
