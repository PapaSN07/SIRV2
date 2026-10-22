import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantFeedbackRequest,
  DatamartSummary,
  RiskListResponse,
  RiskPrediction,
  ScoringJobResponse,
} from '../../../shared/models/assistant.models';

@Injectable({ providedIn: 'root' })
export class AssistantService {
  private readonly apiUrl = `${environment.apiUrl}/assistant`;

  constructor(private readonly http: HttpClient) {}

  listRisks(params: {
    feeder_id?: number;
    risk_level?: string;
    limit?: number;
  } = {}): Observable<RiskListResponse> {
    let httpParams = new HttpParams();
    if (params.feeder_id) httpParams = httpParams.set('feeder_id', params.feeder_id);
    if (params.risk_level) httpParams = httpParams.set('risk_level', params.risk_level);
    if (params.limit) httpParams = httpParams.set('limit', params.limit);
    return this.http
      .get<ApiResponse<RiskListResponse>>(`${this.apiUrl}/risk`, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  getFeederRisk(feederId: number): Observable<RiskPrediction> {
    return this.http
      .get<ApiResponse<RiskPrediction>>(`${this.apiUrl}/risk/feeder/${feederId}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  getDatamart(feederId?: number): Observable<DatamartSummary> {
    let params = new HttpParams();
    if (feederId) params = params.set('feeder_id', feederId);
    return this.http
      .get<ApiResponse<DatamartSummary>>(`${this.apiUrl}/datamart`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  chat(body: AssistantChatRequest): Observable<AssistantChatResponse> {
    return this.http
      .post<ApiResponse<AssistantChatResponse>>(`${this.apiUrl}/chat`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  feedback(conversationId: number, body: AssistantFeedbackRequest): Observable<{ conversation_id: number; accepted: boolean }> {
    return this.http
      .post<ApiResponse<{ conversation_id: number; accepted: boolean }>>(
        `${this.apiUrl}/chat/${conversationId}/feedback`,
        body,
      )
      .pipe(map((res) => this.unwrap(res)));
  }

  runScoring(horizonDays = 90): Observable<ScoringJobResponse> {
    const params = new HttpParams().set('horizon_days', horizonDays);
    return this.http
      .post<ApiResponse<ScoringJobResponse>>(`${this.apiUrl}/scoring/run`, {}, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API Assistant');
    }
    return res.data;
  }
}
