import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  Feeder,
  FeederCreate,
  FeederUpdate,
  Poste,
  PosteCreate,
  PosteSource,
  PosteUpdate,
  ReseauListParams,
} from '../../../shared/models/reseau.models';

@Injectable({ providedIn: 'root' })
export class ReseauAdminDistributionService {
  private readonly apiUrl = `${environment.apiUrl}/reseau`;

  constructor(private readonly http: HttpClient) {}

  listPostesSources(params: ReseauListParams = {}): Observable<PaginatedResponse<PosteSource>> {
    return this.list<PosteSource>('postes-sources', params);
  }

  listFeeders(params: ReseauListParams = {}): Observable<PaginatedResponse<Feeder>> {
    return this.list<Feeder>('feeders', params);
  }

  listPostes(params: ReseauListParams = {}): Observable<PaginatedResponse<Poste>> {
    return this.list<Poste>('postes', params);
  }

  createFeeder(body: FeederCreate): Observable<Feeder> {
    return this.http
      .post<ApiResponse<Feeder>>(`${this.apiUrl}/feeders`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateFeeder(id: number, body: FeederUpdate): Observable<Feeder> {
    return this.http
      .put<ApiResponse<Feeder>>(`${this.apiUrl}/feeders/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  deleteFeeder(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/feeders/${id}`);
  }

  createPoste(body: PosteCreate): Observable<Poste> {
    return this.http
      .post<ApiResponse<Poste>>(`${this.apiUrl}/postes`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updatePoste(id: number, body: PosteUpdate): Observable<Poste> {
    return this.http
      .put<ApiResponse<Poste>>(`${this.apiUrl}/postes/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  deletePoste(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/postes/${id}`);
  }

  private list<T>(resource: string, params: ReseauListParams): Observable<PaginatedResponse<T>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.feeder_id) httpParams = httpParams.set('feeder_id', params.feeder_id);
    if (params.service_id) httpParams = httpParams.set('service_id', params.service_id);
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);

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
