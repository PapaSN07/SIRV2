import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import { BaseClientsResume, TacheLancee } from '../../../shared/models/base-clients.models';

@Injectable({ providedIn: 'root' })
export class BaseClientsService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/clients/contrats`;

  getResume(): Observable<BaseClientsResume> {
    return this.http.get<ApiResponse<BaseClientsResume>>(this.apiUrl).pipe(map((res) => this.unwrap(res)));
  }

  synchroniser(): Observable<TacheLancee> {
    return this.http
      .post<ApiResponse<TacheLancee>>(`${this.apiUrl}/synchroniser`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  importer(fichier: File, annee: number, mois: number): Observable<TacheLancee> {
    const form = new FormData();
    form.append('annee', String(annee));
    form.append('mois', String(mois));
    form.append('fichier', fichier, fichier.name);
    return this.http
      .post<ApiResponse<TacheLancee>>(`${this.apiUrl}/import`, form)
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
