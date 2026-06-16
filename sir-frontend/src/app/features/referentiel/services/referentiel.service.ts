import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  ReferentielItem,
  ReferentielListParams,
  ReferentielResource,
  ReferentielCreate,
  ReferentielUpdate,
} from '../../../shared/models/referentiel.models';

@Injectable({ providedIn: 'root' })
export class ReferentielService {
  private readonly apiUrl = `${environment.apiUrl}/referentiel`;

  constructor(private readonly http: HttpClient) {}

  list(
    resource: ReferentielResource,
    params: ReferentielListParams = {},
  ): Observable<PaginatedResponse<ReferentielItem>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.type_reseau) httpParams = httpParams.set('type_reseau', params.type_reseau);

    return this.http
      .get<ApiResponse<PaginatedResponse<ReferentielItem>>>(`${this.apiUrl}/${resource}`, {
        params: httpParams,
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  create(resource: ReferentielResource, body: ReferentielCreate): Observable<ReferentielItem> {
    return this.http
      .post<ApiResponse<ReferentielItem>>(`${this.apiUrl}/${resource}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  update(
    resource: ReferentielResource,
    id: number,
    body: ReferentielUpdate,
  ): Observable<ReferentielItem> {
    return this.http
      .put<ApiResponse<ReferentielItem>>(`${this.apiUrl}/${resource}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  delete(resource: ReferentielResource, id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${resource}/${id}`);
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
