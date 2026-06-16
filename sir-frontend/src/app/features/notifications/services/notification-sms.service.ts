import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  ManualSmsSendRequest,
  ManualSmsSendResponse,
  NotificationListParams,
  SmsEnvoye,
} from '../../../shared/models/notification.models';

@Injectable({ providedIn: 'root' })
export class NotificationSmsService {
  private readonly apiUrl = `${environment.apiUrl}/notifications/sms`;

  constructor(private readonly http: HttpClient) {}

  list(params: NotificationListParams = {}): Observable<PaginatedResponse<SmsEnvoye>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.entity_type) httpParams = httpParams.set('entity_type', params.entity_type);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);
    if (params.date_debut) httpParams = httpParams.set('date_debut', params.date_debut);
    if (params.date_fin) httpParams = httpParams.set('date_fin', params.date_fin);

    return this.http
      .get<ApiResponse<PaginatedResponse<SmsEnvoye>>>(this.apiUrl, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  get(id: number): Observable<SmsEnvoye> {
    return this.http
      .get<ApiResponse<SmsEnvoye>>(`${this.apiUrl}/${id}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  send(body: ManualSmsSendRequest): Observable<ManualSmsSendResponse> {
    return this.http
      .post<ApiResponse<ManualSmsSendResponse>>(`${this.apiUrl}/send`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
