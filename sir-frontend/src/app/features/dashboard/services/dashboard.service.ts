import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import { HistoriqueResponse, TableauDeBordResponse } from '../../../shared/models/indicateurs.models';

@Injectable({ providedIn: 'root' })
export class DashboardService {
  private readonly apiUrl = `${environment.apiUrl}/indicateurs`;

  constructor(private readonly http: HttpClient) {}

  getTableauDeBord(periode?: string): Observable<TableauDeBordResponse> {
    let params = new HttpParams();
    if (periode) {
      params = params.set('periode', periode);
    }
    return this.http
      .get<ApiResponse<TableauDeBordResponse>>(`${this.apiUrl}/tableau-de-bord`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getHistorique(type: 'saifi' | 'saidi', annees = 1): Observable<HistoriqueResponse> {
    const params = new HttpParams().set('type', type).set('annees', annees);
    return this.http
      .get<ApiResponse<HistoriqueResponse>>(`${this.apiUrl}/historique`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
