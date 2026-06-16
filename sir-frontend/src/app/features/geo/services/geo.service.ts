import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import { Agence, Delegation, Region, Service } from '../../../shared/models/geo.models';

@Injectable({ providedIn: 'root' })
export class GeoService {
  private readonly apiUrl = `${environment.apiUrl}/geo`;

  constructor(private readonly http: HttpClient) {}

  getRegions(): Observable<Region[]> {
    return this.http
      .get<ApiResponse<Region[]>>(`${this.apiUrl}/regions`)
      .pipe(map((res) => this.unwrap(res)));
  }

  getDelegations(regionId: number): Observable<Delegation[]> {
    const params = new HttpParams().set('region_id', regionId);
    return this.http
      .get<ApiResponse<Delegation[]>>(`${this.apiUrl}/delegations`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getAgences(delegationId: number): Observable<Agence[]> {
    const params = new HttpParams().set('delegation_id', delegationId);
    return this.http
      .get<ApiResponse<Agence[]>>(`${this.apiUrl}/agences`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getServices(agenceId: number): Observable<Service[]> {
    const params = new HttpParams().set('agence_id', agenceId);
    return this.http
      .get<ApiResponse<Service[]>>(`${this.apiUrl}/services`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
