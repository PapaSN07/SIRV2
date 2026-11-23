import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../shared/models/api.models';
import {
  CompteursRapprochement,
  FiltreRapprochement,
  LigneRapprochement,
  NoeudSigCourt,
  PosteACreer,
  PosteSchema,
  PostesEntre,
  RapprochementSig,
  SchemaUnifilaire,
  StatutPosteACreer,
  SuggestionCreation,
} from '../../shared/models/schema-unifilaire.models';

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

  // ── Rapprochement Schéma / SIG / SIR ──────────────────────────────────────────

  lignesRapprochement(
    schemaId: number,
    filtre: FiltreRapprochement,
    q: string,
    page: number,
    size: number,
  ): Observable<PaginatedResponse<LigneRapprochement>> {
    let params = new HttpParams().set('filtre', filtre).set('page', page).set('size', size);
    if (q.trim()) params = params.set('q', q.trim());
    return this.http
      .get<ApiResponse<PaginatedResponse<LigneRapprochement>>>(`${this.apiUrl}/${schemaId}/rapprochement`, { params })
      .pipe(map((r) => this.unwrap(r)));
  }

  compteursRapprochement(schemaId: number): Observable<CompteursRapprochement> {
    return this.http
      .get<ApiResponse<CompteursRapprochement>>(`${this.apiUrl}/${schemaId}/rapprochement/compteurs`)
      .pipe(map((r) => this.unwrap(r)));
  }

  rapprocherSig(schemaId: number): Observable<RapprochementSig> {
    return this.http
      .post<ApiResponse<RapprochementSig>>(`${this.apiUrl}/${schemaId}/rapprochement/sig`, {})
      .pipe(map((r) => this.unwrap(r)));
  }

  rechercherSig(q: string): Observable<NoeudSigCourt[]> {
    return this.http
      .get<ApiResponse<NoeudSigCourt[]>>(`${this.apiUrl}/sig/noeuds`, { params: { q } })
      .pipe(map((r) => this.unwrap(r)));
  }

  lierSig(schemaId: number, posteSchemaId: number, noeudSigId: number | null): Observable<LigneRapprochement> {
    return this.http
      .put<ApiResponse<LigneRapprochement>>(`${this.apiUrl}/${schemaId}/rapprochement/${posteSchemaId}/sig`, {
        noeud_sig_id: noeudSigId,
      })
      .pipe(map((r) => this.unwrap(r)));
  }

  lierSir(schemaId: number, posteSchemaId: number, posteId: number | null): Observable<LigneRapprochement> {
    return this.http
      .put<ApiResponse<LigneRapprochement>>(`${this.apiUrl}/${schemaId}/rapprochement/${posteSchemaId}/sir`, {
        poste_id: posteId,
      })
      .pipe(map((r) => this.unwrap(r)));
  }

  statutSir(schemaId: number, posteSchemaId: number, statut: 'inactif' | null): Observable<LigneRapprochement> {
    return this.http
      .put<ApiResponse<LigneRapprochement>>(`${this.apiUrl}/${schemaId}/rapprochement/${posteSchemaId}/statut-sir`, {
        statut_sir: statut,
      })
      .pipe(map((r) => this.unwrap(r)));
  }

  suggestionCreation(schemaId: number, posteSchemaId: number): Observable<SuggestionCreation> {
    return this.http
      .get<ApiResponse<SuggestionCreation>>(`${this.apiUrl}/${schemaId}/rapprochement/${posteSchemaId}/suggestion`)
      .pipe(map((r) => this.unwrap(r)));
  }

  proposerCreation(schemaId: number, posteSchemaId: number, libelle: string, feederId: number): Observable<PosteACreer> {
    return this.http
      .post<ApiResponse<PosteACreer>>(`${this.apiUrl}/${schemaId}/rapprochement/${posteSchemaId}/a-creer`, {
        libelle,
        feeder_id: feederId,
      })
      .pipe(map((r) => this.unwrap(r)));
  }

  postesACreer(statut: StatutPosteACreer, page: number, size: number): Observable<PaginatedResponse<PosteACreer>> {
    return this.http
      .get<ApiResponse<PaginatedResponse<PosteACreer>>>(`${this.apiUrl}/postes-a-creer`, {
        params: { statut, page, size },
      })
      .pipe(map((r) => this.unwrap(r)));
  }

  validerPoste(demandeId: number, code: string | null): Observable<PosteACreer> {
    return this.http
      .post<ApiResponse<PosteACreer>>(`${this.apiUrl}/postes-a-creer/${demandeId}/valider`, { code: code || null })
      .pipe(map((r) => this.unwrap(r)));
  }

  rejeterPoste(demandeId: number, motif: string): Observable<PosteACreer> {
    return this.http
      .post<ApiResponse<PosteACreer>>(`${this.apiUrl}/postes-a-creer/${demandeId}/rejeter`, { motif })
      .pipe(map((r) => this.unwrap(r)));
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Réponse invalide');
    }
    return res.data;
  }
}
