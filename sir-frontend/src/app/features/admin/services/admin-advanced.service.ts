import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  AppSettings,
  AppSettingsUpdate,
  AuditLogEntry,
  RoleDetail,
} from '../../../shared/models/admin.models';

@Injectable({ providedIn: 'root' })
export class AdminAdvancedService {
  private readonly apiUrl = `${environment.apiUrl}/admin`;

  constructor(private readonly http: HttpClient) {}

  listRoles(): Observable<RoleDetail[]> {
    return this.http
      .get<ApiResponse<RoleDetail[]>>(`${this.apiUrl}/roles`)
      .pipe(map((res) => this.unwrap(res)));
  }

  listAuditLog(
    page = 1,
    pageSize = 20,
    tableName?: string,
  ): Observable<PaginatedResponse<AuditLogEntry>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (tableName) params = params.set('table_name', tableName);
    return this.http
      .get<ApiResponse<PaginatedResponse<AuditLogEntry>>>(`${this.apiUrl}/audit-log`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getSettings(): Observable<AppSettings> {
    return this.http
      .get<ApiResponse<AppSettings>>(`${this.apiUrl}/settings`)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateSettings(body: AppSettingsUpdate): Observable<AppSettings> {
    return this.http
      .patch<ApiResponse<AppSettings>>(`${this.apiUrl}/settings`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
