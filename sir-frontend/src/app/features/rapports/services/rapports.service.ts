import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, map, takeWhile, timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { environment } from '../../../../environments/environment';
import { ApiResponse } from '../../../shared/models/api.models';
import {
  ApercuHebdoDD,
  ApercuMensuelDistribution,
  RapportAnnuelParams,
  RapportEnqueueResponse,
  RapportFormat,
  RapportHebdoDDRequest,
  RapportHebdomadaireRequest,
  RapportJournalierRequest,
  RapportMensuelParams,
  RapportStatusResponse,
} from '../../../shared/models/rapports.models';

@Injectable({ providedIn: 'root' })
export class RapportsService {
  private readonly apiUrl = `${environment.apiUrl}/rapports`;

  constructor(private readonly http: HttpClient) {}

  /** Chiffres du rapport hebdomadaire DD pour les graphiques (semaine finissant le vendredi date_fin). */
  getApercuHebdoDD(dateFin?: string): Observable<ApercuHebdoDD> {
    let params = new HttpParams();
    if (dateFin) params = params.set('date_fin', dateFin);
    return this.http
      .get<ApiResponse<ApercuHebdoDD>>(`${this.apiUrl}/apercu/hebdo-dd`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  getApercuMensuelDistribution(annee: number, mois: number, regionId?: number | null): Observable<ApercuMensuelDistribution> {
    let params = new HttpParams().set('annee', annee).set('mois', mois);
    if (regionId) params = params.set('region_id', regionId);
    return this.http
      .get<ApiResponse<ApercuMensuelDistribution>>(`${this.apiUrl}/apercu/mensuel-distribution`, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueJournalier(body: RapportJournalierRequest): Observable<RapportEnqueueResponse> {
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(`${this.apiUrl}/journalier`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueHebdomadaire(body: RapportHebdomadaireRequest): Observable<RapportEnqueueResponse> {
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(`${this.apiUrl}/hebdomadaire`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueHebdoDD(body: RapportHebdoDDRequest): Observable<RapportEnqueueResponse> {
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(`${this.apiUrl}/hebdo-dd`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueMensuelDistribution(params: RapportMensuelParams): Observable<RapportEnqueueResponse> {
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(
        `${this.apiUrl}/mensuel/distribution`,
        {},
        { params: this.mensuelParams(params) },
      )
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueMensuelTransport(params: RapportMensuelParams): Observable<RapportEnqueueResponse> {
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(
        `${this.apiUrl}/mensuel/transport`,
        {},
        { params: this.mensuelParams(params, false) },
      )
      .pipe(map((res) => this.unwrap(res)));
  }

  enqueueAnnuel(params: RapportAnnuelParams): Observable<RapportEnqueueResponse> {
    let httpParams = new HttpParams()
      .set('annee', params.annee)
      .set('direction', params.direction ?? 'distribution')
      .set('format', params.format ?? 'pdf')
      .set('limit', params.limit ?? 10);
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    return this.http
      .post<ApiResponse<RapportEnqueueResponse>>(`${this.apiUrl}/annuel`, {}, { params: httpParams })
      .pipe(map((res) => this.unwrap(res)));
  }

  getStatus(taskId: string): Observable<RapportStatusResponse> {
    return this.http
      .get<ApiResponse<RapportStatusResponse>>(`${this.apiUrl}/${taskId}/status`)
      .pipe(map((res) => this.unwrap(res)));
  }

  pollStatus(taskId: string, intervalMs = 3000, maxPolls = 60): Observable<RapportStatusResponse> {
    return timer(0, intervalMs).pipe(
      takeWhile((n) => n < maxPolls, true),
      switchMap(() => this.getStatus(taskId)),
      takeWhile((s) => s.statut === 'pending' || s.statut === 'started', true),
    );
  }

  download(taskId: string, format?: RapportFormat): Observable<Blob> {
    let params = new HttpParams();
    if (format) params = params.set('format', format);
    return this.http.get(`${this.apiUrl}/${taskId}/download`, { params, responseType: 'blob' });
  }

  /** PDF du rapport généré, pour l'afficher dans la page avant de le télécharger. */
  apercuPdf(taskId: string): Observable<Blob> {
    return this.http.get(`${this.apiUrl}/${taskId}/apercu`, { responseType: 'blob' });
  }

  private mensuelParams(params: RapportMensuelParams, withRegion = true): HttpParams {
    let httpParams = new HttpParams()
      .set('annee', params.annee)
      .set('mois', params.mois)
      .set('format', params.format ?? 'pdf')
      .set('limit', params.limit ?? 10);
    if (withRegion && params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    return httpParams;
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
