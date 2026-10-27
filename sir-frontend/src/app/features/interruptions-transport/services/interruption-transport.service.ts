import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  InterruptionClotureRequest,
  InterruptionTransport,
  InterruptionTransportCreate,
  InterruptionTransportDetail,
  InterruptionTransportListParams,
  InterruptionTransportUpdate,
} from '../../../shared/models/interruption-transport.models';
import { MotifRequest, StatutHistorique } from '../../../shared/models/interruption.models';

@Injectable({ providedIn: 'root' })
export class InterruptionTransportService {
  private readonly apiUrl = `${environment.apiUrl}/interruptions/transport`;

  constructor(private readonly http: HttpClient) {}

  list(params: InterruptionTransportListParams = {}): Observable<PaginatedResponse<InterruptionTransport>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.type_direction) httpParams = httpParams.set('type_direction', params.type_direction);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);
    if (params.date_debut) httpParams = httpParams.set('date_debut', params.date_debut);
    if (params.date_fin) httpParams = httpParams.set('date_fin', params.date_fin);
    if (params.equipement_transport_id) {
      httpParams = httpParams.set('equipement_transport_id', params.equipement_transport_id);
    }
    if (params.source_transport_id) {
      httpParams = httpParams.set('source_transport_id', params.source_transport_id);
    }

    return this.http
      .get<ApiResponse<PaginatedResponse<InterruptionTransport>>>(this.apiUrl, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  get(id: number): Observable<InterruptionTransportDetail> {
    return this.http
      .get<ApiResponse<InterruptionTransportDetail>>(`${this.apiUrl}/${id}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  create(body: InterruptionTransportCreate): Observable<InterruptionTransport> {
    return this.http
      .post<ApiResponse<InterruptionTransport>>(this.apiUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  update(id: number, body: InterruptionTransportUpdate): Observable<InterruptionTransport> {
    return this.http
      .put<ApiResponse<InterruptionTransport>>(`${this.apiUrl}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  cloturer(id: number, body: InterruptionClotureRequest): Observable<InterruptionTransport> {
    return this.http
      .patch<ApiResponse<InterruptionTransport>>(`${this.apiUrl}/${id}/cloturer`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  valider(id: number): Observable<InterruptionTransport> {
    return this.http
      .patch<ApiResponse<InterruptionTransport>>(`${this.apiUrl}/${id}/valider`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }

  /** Admin Dispatching : clôturée → en cours, motif envoyé au saisisseur. */
  renvoyer(id: number, body: MotifRequest): Observable<InterruptionTransportDetail> {
    return this.http
      .patch<ApiResponse<InterruptionTransportDetail>>(`${this.apiUrl}/${id}/renvoyer`, body)
      .pipe(map((res) => this.unwrapResponse(res)));
  }

  /** Admin Dispatching : validée → clôturée (impossible après archivage). */
  devalider(id: number, body: MotifRequest): Observable<InterruptionTransportDetail> {
    return this.http
      .patch<ApiResponse<InterruptionTransportDetail>>(`${this.apiUrl}/${id}/devalider`, body)
      .pipe(map((res) => this.unwrapResponse(res)));
  }

  historiqueStatuts(id: number): Observable<StatutHistorique[]> {
    return this.http
      .get<ApiResponse<StatutHistorique[]>>(`${this.apiUrl}/${id}/historique-statuts`)
      .pipe(map((res) => this.unwrapResponse(res)));
  }

  private unwrapResponse<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
