import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, catchError, from, map, switchMap, throwError } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  InterruptionClotureRequest,
  InterruptionDistribution,
  InterruptionDistributionCreate,
  InterruptionDistributionDetail,
  InterruptionDistributionStats,
  InterruptionDistributionUpdate,
  InterruptionListParams,
  InterruptionWorkflow,
  PosteImpacte,
  PosteImpacteBulk,
  PosteImpacteFromSigRequest,
  PosteInterruptionCreate,
  WorkflowEtapeUpdate,
  ArchivageRequest,
  ArchivageResponse,
  ValidationLotResponse,
  FisImportResponse,
  MotifRequest,
  StatutHistorique,
} from '../../../shared/models/interruption.models';

@Injectable({ providedIn: 'root' })
export class InterruptionDistributionService {
  private readonly apiUrl = `${environment.apiUrl}/interruptions/distribution`;

  constructor(private readonly http: HttpClient) {}

  list(params: InterruptionListParams = {}): Observable<PaginatedResponse<InterruptionDistribution>> {
    let httpParams = new HttpParams();
    if (params.page) httpParams = httpParams.set('page', params.page);
    if (params.page_size) httpParams = httpParams.set('page_size', params.page_size);
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    if (params.service_id) httpParams = httpParams.set('service_id', params.service_id);
    if (params.feeder_id) httpParams = httpParams.set('feeder_id', params.feeder_id);
    if (params.nature_id) httpParams = httpParams.set('nature_id', params.nature_id);
    if (params.ouverture) httpParams = httpParams.set('ouverture', params.ouverture);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);
    if (params.date_debut) httpParams = httpParams.set('date_debut', params.date_debut);
    if (params.date_fin) httpParams = httpParams.set('date_fin', params.date_fin);

    return this.http
      .get<ApiResponse<PaginatedResponse<InterruptionDistribution>>>(this.apiUrl, {
        params: httpParams,
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  stats(params: InterruptionListParams = {}): Observable<InterruptionDistributionStats> {
    let httpParams = new HttpParams();
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    if (params.service_id) httpParams = httpParams.set('service_id', params.service_id);
    if (params.feeder_id) httpParams = httpParams.set('feeder_id', params.feeder_id);
    if (params.nature_id) httpParams = httpParams.set('nature_id', params.nature_id);
    if (params.ouverture) httpParams = httpParams.set('ouverture', params.ouverture);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);
    if (params.date_debut) httpParams = httpParams.set('date_debut', params.date_debut);
    if (params.date_fin) httpParams = httpParams.set('date_fin', params.date_fin);

    return this.http
      .get<ApiResponse<InterruptionDistributionStats>>(`${this.apiUrl}/stats`, {
        params: httpParams,
      })
      .pipe(map((res) => this.unwrap(res)));
  }

  get(id: number): Observable<InterruptionDistributionDetail> {
    return this.http
      .get<ApiResponse<InterruptionDistributionDetail>>(`${this.apiUrl}/${id}`)
      .pipe(map((res) => this.unwrap(res)));
  }

  create(body: InterruptionDistributionCreate): Observable<InterruptionDistribution> {
    return this.http
      .post<ApiResponse<InterruptionDistribution>>(this.apiUrl, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  update(id: number, body: InterruptionDistributionUpdate): Observable<InterruptionDistribution> {
    return this.http
      .put<ApiResponse<InterruptionDistribution>>(`${this.apiUrl}/${id}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  cloturer(id: number, body: InterruptionClotureRequest): Observable<InterruptionDistribution> {
    return this.http
      .patch<ApiResponse<InterruptionDistribution>>(`${this.apiUrl}/${id}/cloturer`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  valider(id: number): Observable<InterruptionDistribution> {
    return this.http
      .patch<ApiResponse<InterruptionDistribution>>(`${this.apiUrl}/${id}/valider`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  /** Import FIS : `simulation` contrôle le fichier sans rien enregistrer. */
  importerFis(fichier: File, simulation: boolean, ignorerDoublons = true): Observable<FisImportResponse> {
    const form = new FormData();
    form.append('file', fichier, fichier.name);
    const params = new HttpParams()
      .set('simulation', simulation)
      .set('skip_existing', ignorerDoublons);
    return this.http
      .post<ApiResponse<FisImportResponse>>(`${this.apiUrl}/import-fis`, form, { params })
      .pipe(map((res) => this.unwrap(res)));
  }

  /** Fichier Excel ou PDF de la liste filtrée (5 000 lignes max., même périmètre que l'écran). */
  exporter(
    params: InterruptionListParams,
    format: 'xlsx' | 'pdf',
    libelle: string,
  ): Observable<{ blob: Blob; nom: string }> {
    let httpParams = new HttpParams().set('format', format).set('libelle', libelle);
    if (params.region_id) httpParams = httpParams.set('region_id', params.region_id);
    if (params.service_id) httpParams = httpParams.set('service_id', params.service_id);
    if (params.feeder_id) httpParams = httpParams.set('feeder_id', params.feeder_id);
    if (params.nature_id) httpParams = httpParams.set('nature_id', params.nature_id);
    if (params.ouverture) httpParams = httpParams.set('ouverture', params.ouverture);
    if (params.statut) httpParams = httpParams.set('statut', params.statut);
    if (params.date_debut) httpParams = httpParams.set('date_debut', params.date_debut);
    if (params.date_fin) httpParams = httpParams.set('date_fin', params.date_fin);
    return this.http
      .get(`${this.apiUrl}/export`, { params: httpParams, responseType: 'blob', observe: 'response' })
      .pipe(
        map((res) => {
          const disposition = res.headers.get('Content-Disposition') ?? '';
          const nom = /filename="([^"]+)"/.exec(disposition)?.[1] ?? `interruptions.${format}`;
          return { blob: res.body ?? new Blob(), nom };
        }),
        // Réponse d'erreur reçue en Blob : on relit le JSON pour garder le message métier
        catchError((err: HttpErrorResponse) => {
          if (!(err.error instanceof Blob)) return throwError(() => err);
          return from(err.error.text()).pipe(
            switchMap((texte) => {
              let message = err.message;
              try {
                const body = JSON.parse(texte) as { error?: string; detail?: { error?: string } };
                message = body.detail?.error ?? body.error ?? message;
              } catch {
                /* corps non JSON : message générique de l'intercepteur */
              }
              return throwError(() => new Error(message));
            }),
          );
        }),
      );
  }

  /** Validation de plusieurs interruptions en une requête, résultat ligne par ligne. */
  validerLot(ids: number[]): Observable<ValidationLotResponse> {
    return this.http
      .post<ApiResponse<ValidationLotResponse>>(`${this.apiUrl}/valider-lot`, { ids })
      .pipe(map((res) => this.unwrap(res)));
  }

  /** Admin SCR : clôturée → en cours, motif affiché au saisisseur. */
  renvoyer(id: number, body: MotifRequest): Observable<InterruptionDistribution> {
    return this.http
      .patch<ApiResponse<InterruptionDistribution>>(`${this.apiUrl}/${id}/renvoyer`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  /** Admin SCR : validée → clôturée (impossible après archivage). */
  devalider(id: number, body: MotifRequest): Observable<InterruptionDistribution> {
    return this.http
      .patch<ApiResponse<InterruptionDistribution>>(`${this.apiUrl}/${id}/devalider`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  historiqueStatuts(id: number): Observable<StatutHistorique[]> {
    return this.http
      .get<ApiResponse<StatutHistorique[]>>(`${this.apiUrl}/${id}/historique-statuts`)
      .pipe(map((res) => this.unwrap(res)));
  }

  /** Gel des interruptions validées d'un mois, après le rapport mensuel CRSE. */
  archiverMois(body: ArchivageRequest): Observable<ArchivageResponse> {
    return this.http
      .post<ApiResponse<ArchivageResponse>>(`${this.apiUrl}/archiver`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  listPostes(id: number): Observable<PosteImpacte[]> {
    return this.http
      .get<ApiResponse<PosteImpacte[]>>(`${this.apiUrl}/${id}/postes`)
      .pipe(map((res) => this.unwrap(res)));
  }

  addPoste(id: number, body: PosteInterruptionCreate): Observable<PosteImpacte> {
    return this.http
      .post<ApiResponse<PosteImpacte>>(`${this.apiUrl}/${id}/postes`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  addPostesFromFeeder(id: number): Observable<PosteImpacteBulk> {
    return this.http
      .post<ApiResponse<PosteImpacteBulk>>(`${this.apiUrl}/${id}/postes/from-feeder`, {})
      .pipe(map((res) => this.unwrap(res)));
  }

  addPostesFromSigTroncon(
    id: number,
    body: PosteImpacteFromSigRequest = {},
  ): Observable<PosteImpacteBulk> {
    return this.http
      .post<ApiResponse<PosteImpacteBulk>>(`${this.apiUrl}/${id}/postes/from-sig-troncon`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  removePoste(id: number, posteId: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}/postes/${posteId}`);
  }

  getWorkflow(id: number): Observable<InterruptionWorkflow> {
    return this.http
      .get<ApiResponse<InterruptionWorkflow>>(`${this.apiUrl}/${id}/workflow`)
      .pipe(map((res) => this.unwrap(res)));
  }

  updateWorkflowEtape(
    id: number,
    etapeId: number,
    body: WorkflowEtapeUpdate,
  ): Observable<InterruptionWorkflow> {
    return this.http
      .put<ApiResponse<InterruptionWorkflow>>(`${this.apiUrl}/${id}/workflow/etapes/${etapeId}`, body)
      .pipe(map((res) => this.unwrap(res)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
