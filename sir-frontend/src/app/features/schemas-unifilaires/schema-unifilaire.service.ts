import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api.models';
import { PosteSchema, PostesEntre, SchemaUnifilaire } from '../../shared/models/schema-unifilaire.models';

@Injectable({ providedIn: 'root' })
export class SchemaUnifilaireService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/schemas-unifilaires`;

  lister(): Observable<SchemaUnifilaire[]> {
    return this.http.get<ApiResponse<SchemaUnifilaire[]>>(this.apiUrl).pipe(map((r) => this.unwrap(r)));
  }

  postes(schemaId: number): Observable<PosteSchema[]> {
    return this.http
      .get<ApiResponse<PosteSchema[]>>(`${this.apiUrl}/${schemaId}/postes`)
      .pipe(map((r) => this.unwrap(r)));
  }

  /** Tuile PNG ; null pour une zone blanche (204). Passe par HttpClient : jeton d'accès joint. */
  tuile(schemaId: number, z: number, x: number, y: number): Observable<Blob | null> {
    return this.http
      .get(`${this.apiUrl}/${schemaId}/tuiles/${z}/${x}/${y}`, { responseType: 'blob', observe: 'response' })
      .pipe(map((res) => (res.status === 204 || !res.body || res.body.size === 0 ? null : res.body)));
  }

  entre(schemaId: number, debutId: number, finId: number): Observable<PostesEntre> {
    return this.http
      .post<ApiResponse<PostesEntre>>(`${this.apiUrl}/${schemaId}/entre`, { debut_id: debutId, fin_id: finId })
      .pipe(map((r) => this.unwrap(r)));
  }

  associer(schemaId: number, posteSchemaId: number, posteId: number | null): Observable<PosteSchema> {
    return this.http
      .put<ApiResponse<PosteSchema>>(`${this.apiUrl}/${schemaId}/postes/${posteSchemaId}`, { poste_id: posteId })
      .pipe(map((r) => this.unwrap(r)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Réponse invalide');
    }
    return res.data;
  }
}
