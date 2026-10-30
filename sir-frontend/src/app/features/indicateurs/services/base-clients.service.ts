import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  ActionAtelier,
  BaseClientsResume,
  DroitsAtelier,
  LienPosteUR,
  LienPosteURCreate,
  LiensQuery,
  PosteRecherche,
  TacheLancee,
  UniteReleveRecherche,
} from '../../../shared/models/base-clients.models';

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

  // ── Atelier : lien poste ↔ unité de relève ──

  private readonly atelierUrl = `${environment.apiUrl}/clients/atelier`;

  getDroits(): Observable<DroitsAtelier> {
    return this.http.get<ApiResponse<DroitsAtelier>>(`${this.atelierUrl}/droits`).pipe(map((res) => this.unwrap(res)));
  }

  getLiens(q: LiensQuery): Observable<PaginatedResponse<LienPosteUR>> {
    let params = new HttpParams().set('page', q.page).set('page_size', q.page_size);
    if (q.poste_id) params = params.set('poste_id', q.poste_id);
    if (q.a_valider) params = params.set('a_valider', 'true');
    if (q.recherche?.trim()) params = params.set('recherche', q.recherche.trim());
    return this.http
      .get<ApiResponse<PaginatedResponse<LienPosteUR>>>(`${this.atelierUrl}/liens`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  rechercherPostes(recherche: string): Observable<PosteRecherche[]> {
    const params = new HttpParams().set('recherche', recherche);
    return this.http
      .get<ApiResponse<PosteRecherche[]>>(`${this.atelierUrl}/postes`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  rechercherUr(recherche: string): Observable<UniteReleveRecherche[]> {
    const params = new HttpParams().set('recherche', recherche);
    return this.http
      .get<ApiResponse<UniteReleveRecherche[]>>(`${this.atelierUrl}/unites-releve`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  proposerAjout(data: LienPosteURCreate): Observable<ActionAtelier> {
    return this.http
      .post<ApiResponse<ActionAtelier>>(`${this.atelierUrl}/liens`, data)
      .pipe(map((res) => this.unwrap(res)));
  }

  proposerRetrait(id: number): Observable<ActionAtelier> {
    return this.http
      .delete<ApiResponse<ActionAtelier>>(`${this.atelierUrl}/liens/${id}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  decider(id: number, accepter: boolean): Observable<ActionAtelier> {
    const action = accepter ? 'valider' : 'rejeter';
    return this.http
      .post<ApiResponse<ActionAtelier>>(`${this.atelierUrl}/liens/${id}/${action}`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
