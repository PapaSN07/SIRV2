import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import {
  EndIndicateurResponse,
  HistoriqueResponse,
  IndicateurHistoriqueType,
  IndicateursQueryParams,
  SaifiIndicateurResponse,
  SaidiIndicateurResponse,
  ObjectifsPilotageUpdate,
  PilotageResponse,
  TableauDeBordResponse,
  TendanceResponse,
  TopFeedersResponse,
} from '../../../shared/models/indicateurs.models';

@Injectable({ providedIn: 'root' })
export class IndicateursService {
  private readonly apiUrl = `${environment.apiUrl}/indicateurs`;

  constructor(private readonly http: HttpClient) {}

  getTableauDeBord(params: IndicateursQueryParams = {}): Observable<TableauDeBordResponse> {
    return this.http
      .get<ApiResponse<TableauDeBordResponse>>(`${this.apiUrl}/tableau-de-bord`, {
        params: this.buildParams(params),
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  getHistorique(
    type: IndicateurHistoriqueType,
    annees = 1,
    regionId?: number,
  ): Observable<HistoriqueResponse> {
    let params = new HttpParams().set('type', type).set('annees', annees);
    if (regionId) params = params.set('region_id', regionId);
    return this.http
      .get<ApiResponse<HistoriqueResponse>>(`${this.apiUrl}/historique`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getEnd(params: IndicateursQueryParams & { include_services?: boolean }): Observable<EndIndicateurResponse> {
    let httpParams = this.buildParams(params);
    if (params.include_services) httpParams = httpParams.set('include_services', 'true');
    return this.http
      .get<ApiResponse<EndIndicateurResponse>>(`${this.apiUrl}/end`, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  getSaifi(params: IndicateursQueryParams): Observable<SaifiIndicateurResponse> {
    return this.http
      .get<ApiResponse<SaifiIndicateurResponse>>(`${this.apiUrl}/saifi`, { params: this.buildParams(params) })
      .pipe(map((res) => this.unwrap(res)));
  }

  getSaidi(params: IndicateursQueryParams): Observable<SaidiIndicateurResponse> {
    return this.http
      .get<ApiResponse<SaidiIndicateurResponse>>(`${this.apiUrl}/saidi`, { params: this.buildParams(params) })
      .pipe(map((res) => this.unwrap(res)));
  }

  getPilotage(params: IndicateursQueryParams = {}): Observable<PilotageResponse> {
    return this.http
      .get<ApiResponse<PilotageResponse>>(`${this.apiUrl}/pilotage`, {
        params: this.buildParams(params),
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  saveObjectifs(body: ObjectifsPilotageUpdate): Observable<PilotageResponse> {
    return this.http
      .put<ApiResponse<PilotageResponse>>(`${this.apiUrl}/pilotage/objectifs`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  getTendance(
    cible: 'feeder' | 'poste',
    cibleId: number,
    annees = 3,
  ): Observable<TendanceResponse> {
    const params = new HttpParams()
      .set('cible', cible)
      .set('cible_id', cibleId)
      .set('annees', annees);
    return this.http
      .get<ApiResponse<TendanceResponse>>(`${this.apiUrl}/pilotage/tendance`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getTopFeeders(params: IndicateursQueryParams & { limit?: number }): Observable<TopFeedersResponse> {
    let httpParams = this.buildParams(params);
    if (params.limit) httpParams = httpParams.set('limit', params.limit);
    return this.http
      .get<ApiResponse<TopFeedersResponse>>(`${this.apiUrl}/top-feeders`, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  private buildParams(params: IndicateursQueryParams): HttpParams {
    let httpParams = new HttpParams();
    if (params.periode) httpParams = httpParams.set('periode', params.periode);
    if (params.annee) httpParams = httpParams.set('annee', params.annee);
    if (params.mois) httpParams = httpParams.set('mois', params.mois);
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    return httpParams;
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
