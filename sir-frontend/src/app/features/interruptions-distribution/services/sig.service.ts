import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import { SigListParams, TronconSig, TronconSigChaine } from '../../../shared/models/sig.models';

@Injectable({ providedIn: 'root' })
export class SigService {
  private readonly apiUrl = `${environment.apiUrl}/reseau/sig`;

  constructor(private readonly http: HttpClient) {}

  listTroncons(params: SigListParams): Observable<PaginatedResponse<TronconSig>> {
    let httpParams = new HttpParams().set('feeder_id', params.feeder_id);
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.search) httpParams = httpParams.set('search', params.search);

    return this.http
      .get<ApiResponse<PaginatedResponse<TronconSig>>>(`${this.apiUrl}/troncons`, {
        params: httpParams,
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  getChaineAval(tronconSigId: number, limit = 3): Observable<TronconSigChaine> {
    const params = new HttpParams().set('limit', limit);
    return this.http
      .get<ApiResponse<TronconSigChaine>>(`${this.apiUrl}/troncons/${tronconSigId}/chaine-aval`, {
        params,
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
