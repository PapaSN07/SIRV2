import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import { NaptCreate, NaptItem } from '../../../shared/models/napt.models';

@Injectable({ providedIn: 'root' })
export class NaptService {
  private readonly apiUrl = `${environment.apiUrl}/napt`;

  constructor(private readonly http: HttpClient) {}

  list(page = 1, pageSize = 20, statut?: string): Observable<PaginatedResponse<NaptItem>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (statut) params = params.set('statut', statut);
    return this.http
      .get<ApiResponse<PaginatedResponse<NaptItem>>>(this.apiUrl, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  get(id: number): Observable<NaptItem> {
    return this.http
      .get<ApiResponse<NaptItem>>(`${this.apiUrl}/${id}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  create(body: NaptCreate): Observable<NaptItem> {
    return this.http
      .post<ApiResponse<NaptItem>>(this.apiUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  soumettre(id: number): Observable<NaptItem> {
    return this.http
      .patch<ApiResponse<NaptItem>>(`${this.apiUrl}/${id}/soumettre`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  valider(id: number): Observable<NaptItem> {
    return this.http
      .patch<ApiResponse<NaptItem>>(`${this.apiUrl}/${id}/valider`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  cloturer(id: number): Observable<NaptItem> {
    return this.http
      .patch<ApiResponse<NaptItem>>(`${this.apiUrl}/${id}/cloturer`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
