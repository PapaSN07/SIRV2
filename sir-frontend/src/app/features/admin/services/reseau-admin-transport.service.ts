import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  EquipementTransport,
  EquipementTransportCreate,
  EquipementTransportUpdate,
  ReseauTransportListParams,
  SourceTransport,
  SourceTransportCreate,
  SourceTransportUpdate,
} from '../../../shared/models/reseau-transport.models';

@Injectable({ providedIn: 'root' })
export class ReseauAdminTransportService {
  private readonly apiUrl = `${environment.apiUrl}/reseau/transport`;

  constructor(private readonly http: HttpClient) {}

  listEquipements(
    params: ReseauTransportListParams = {},
  ): Observable<PaginatedResponse<EquipementTransport>> {
    return this.list<EquipementTransport>('equipements-transport', params);
  }

  listSources(params: ReseauTransportListParams = {}): Observable<PaginatedResponse<SourceTransport>> {
    return this.list<SourceTransport>('sources-transport', params);
  }

  createEquipement(body: EquipementTransportCreate): Observable<EquipementTransport> {
    return this.http
      .post<ApiResponse<EquipementTransport>>(`${this.apiUrl}/equipements-transport`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateEquipement(id: number, body: EquipementTransportUpdate): Observable<EquipementTransport> {
    return this.http
      .put<ApiResponse<EquipementTransport>>(`${this.apiUrl}/equipements-transport/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  deleteEquipement(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/equipements-transport/${id}`);
  }

  createSource(body: SourceTransportCreate): Observable<SourceTransport> {
    return this.http
      .post<ApiResponse<SourceTransport>>(`${this.apiUrl}/sources-transport`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateSource(id: number, body: SourceTransportUpdate): Observable<SourceTransport> {
    return this.http
      .put<ApiResponse<SourceTransport>>(`${this.apiUrl}/sources-transport/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  deleteSource(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/sources-transport/${id}`);
  }

  private list<T>(resource: string, params: ReseauTransportListParams): Observable<PaginatedResponse<T>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.type_equipement) httpParams = httpParams.set('type_equipement', params.type_equipement);
    if (params.equipement_transport_id) {
      httpParams = httpParams.set('equipement_transport_id', params.equipement_transport_id);
    }

    return this.http
      .get<ApiResponse<PaginatedResponse<T>>>(`${this.apiUrl}/${resource}`, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
