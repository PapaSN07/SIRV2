import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  Destinataire,
  DestinataireCreate,
  DestinataireUpdate,
  EmailEnvoye,
  GroupeEnvoi,
  GroupeEnvoiCreate,
  GroupeEnvoiUpdate,
  NotificationListParams,
} from '../../../shared/models/notification.models';

@Injectable({ providedIn: 'root' })
export class NotificationDestinataireService {
  private readonly destUrl = `${environment.apiUrl}/notifications/destinataires`;
  private readonly emailUrl = `${environment.apiUrl}/notifications/emails`;
  private readonly groupesUrl = `${environment.apiUrl}/notifications/groupes-envoi`;

  constructor(private readonly http: HttpClient) {}

  listGroupesEnvoi(inclureInactifs = false): Observable<GroupeEnvoi[]> {
    const params = new HttpParams().set('inclure_inactifs', inclureInactifs);
    return this.http
      .get<ApiResponse<GroupeEnvoi[]>>(this.groupesUrl, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  createGroupe(body: GroupeEnvoiCreate): Observable<GroupeEnvoi> {
    return this.http
      .post<ApiResponse<GroupeEnvoi>>(this.groupesUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateGroupe(id: number, body: GroupeEnvoiUpdate): Observable<GroupeEnvoi> {
    return this.http
      .patch<ApiResponse<GroupeEnvoi>>(`${this.groupesUrl}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  listDestinataires(
    page = 1,
    pageSize = 100,
    isActive?: boolean,
    filtres: { groupeId?: number | null; recherche?: string } = {},
  ): Observable<PaginatedResponse<Destinataire>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (isActive !== undefined) params = params.set('is_active', isActive);
    if (filtres.groupeId) params = params.set('groupe_id', filtres.groupeId);
    if (filtres.recherche?.trim()) params = params.set('recherche', filtres.recherche.trim());

    return this.http
      .get<ApiResponse<PaginatedResponse<Destinataire>>>(this.destUrl, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  create(body: DestinataireCreate): Observable<Destinataire> {
    return this.http
      .post<ApiResponse<Destinataire>>(this.destUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  update(id: number, body: DestinataireUpdate): Observable<Destinataire> {
    return this.http
      .patch<ApiResponse<Destinataire>>(`${this.destUrl}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  delete(id: number): Observable<void> {
    return this.http.delete<void>(`${this.destUrl}/${id}`);
  }

  listEmails(params: NotificationListParams = {}): Observable<PaginatedResponse<EmailEnvoye>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);

    return this.http
      .get<ApiResponse<PaginatedResponse<EmailEnvoye>>>(this.emailUrl, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
