import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  ResetPasswordRequest,
  UtilisateurAdmin,
  UtilisateurCreate,
  UtilisateurUpdate,
} from '../../../shared/models/admin.models';

@Injectable({ providedIn: 'root' })
export class AdminUtilisateurService {
  private readonly apiUrl = `${environment.apiUrl}/admin/utilisateurs`;

  constructor(private readonly http: HttpClient) {}

  list(page = 1, pageSize = 20): Observable<PaginatedResponse<UtilisateurAdmin>> {
    const params = new HttpParams().set('page', page).set('page_size', pageSize);
    return this.http
      .get<ApiResponse<PaginatedResponse<UtilisateurAdmin>>>(this.apiUrl, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  create(body: UtilisateurCreate): Observable<UtilisateurAdmin> {
    return this.http
      .post<ApiResponse<UtilisateurAdmin>>(this.apiUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  update(id: number, body: UtilisateurUpdate): Observable<UtilisateurAdmin> {
    return this.http
      .put<ApiResponse<UtilisateurAdmin>>(`${this.apiUrl}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  activer(id: number): Observable<UtilisateurAdmin> {
    return this.http
      .patch<ApiResponse<UtilisateurAdmin>>(`${this.apiUrl}/${id}/activer`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  desactiver(id: number): Observable<UtilisateurAdmin> {
    return this.http
      .patch<ApiResponse<UtilisateurAdmin>>(`${this.apiUrl}/${id}/desactiver`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  resetPassword(id: number, body: ResetPasswordRequest): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/${id}/reset-password`, body);
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
