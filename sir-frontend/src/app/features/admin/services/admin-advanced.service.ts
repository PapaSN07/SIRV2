import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  AnnuaireUtilisateur,
  AppSettings,
  AppSettingsUpdate,
  AuditLogEntry,
  ObjectifsAdmin,
  ObjectifsAdminUpdate,
  PermissionInfo,
  RoleCreate,
  RoleDetail,
  RoleUpdate,
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

  listPermissions(): Observable<PermissionInfo[]> {
    return this.http
      .get<ApiResponse<PermissionInfo[]>>(`${this.apiUrl}/permissions`)
      .pipe(map((res) => this.unwrap(res)));
  }

  createRole(body: RoleCreate): Observable<RoleDetail> {
    return this.http
      .post<ApiResponse<RoleDetail>>(`${this.apiUrl}/roles`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateRole(id: number, body: RoleUpdate): Observable<RoleDetail> {
    return this.http
      .put<ApiResponse<RoleDetail>>(`${this.apiUrl}/roles/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  rechercherAnnuaire(q: string): Observable<AnnuaireUtilisateur[]> {
    return this.http
      .get<ApiResponse<AnnuaireUtilisateur[]>>(`${this.apiUrl}/annuaire`, { params: { q } })
      .pipe(map((res) => this.unwrap(res)));
  }

  getObjectifs(annee: number): Observable<ObjectifsAdmin> {
    return this.http
      .get<ApiResponse<ObjectifsAdmin>>(`${environment.apiUrl}/indicateurs/pilotage/objectifs/admin`, {
        params: { annee },
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  saveObjectifs(body: ObjectifsAdminUpdate): Observable<ObjectifsAdmin> {
    return this.http
      .put<ApiResponse<ObjectifsAdmin>>(`${environment.apiUrl}/indicateurs/pilotage/objectifs/admin`, body)
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
