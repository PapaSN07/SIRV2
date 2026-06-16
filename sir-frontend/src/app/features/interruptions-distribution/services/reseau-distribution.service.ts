import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import { Feeder, Poste, ReseauListParams } from '../../../shared/models/reseau.models';

@Injectable({ providedIn: 'root' })
export class ReseauDistributionService {
  private readonly apiUrl = `${environment.apiUrl}/reseau`;

  constructor(private readonly http: HttpClient) {}

  listFeeders(params: ReseauListParams = {}): Observable<PaginatedResponse<Feeder>> {
    return this.list<Feeder>('feeders', params);
  }

  listPostes(params: ReseauListParams = {}): Observable<PaginatedResponse<Poste>> {
    return this.list<Poste>('postes', params);
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
