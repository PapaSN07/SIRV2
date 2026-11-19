import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ApiResponse, PaginatedResponse } from '../../../shared/models/api.models';
import {
  FeederSig,
  NoeudSigAdmin,
  SigListeParams,
  StationSig,
  SyntheseSig,
  TronconSigAdmin,
} from '../../../shared/models/sig.models';

/** Consultation de la topologie SIG (lecture seule). */
@Injectable({ providedIn: 'root' })
export class SigAdminService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = `${environment.apiUrl}/reseau/sig/admin`;

  synthese(): Observable<SyntheseSig> {
    return this.get<SyntheseSig>('synthese', {});
  }

  stations(params: SigListeParams): Observable<PaginatedResponse<StationSig>> {
    return this.get<PaginatedResponse<StationSig>>('stations', params);
  }

  feeders(params: SigListeParams): Observable<PaginatedResponse<FeederSig>> {
    return this.get<PaginatedResponse<FeederSig>>('feeders', params);
  }

  troncons(params: SigListeParams): Observable<PaginatedResponse<TronconSigAdmin>> {
    return this.get<PaginatedResponse<TronconSigAdmin>>('troncons', params);
  }

  noeuds(params: SigListeParams): Observable<PaginatedResponse<NoeudSigAdmin>> {
    return this.get<PaginatedResponse<NoeudSigAdmin>>('noeuds', params);
  }

  carte(params: { nom_feeder?: string; station?: string }): Observable<NoeudSigAdmin[]> {
    return this.get<NoeudSigAdmin[]>('carte', params);
  }

  private get<T>(chemin: string, params: object): Observable<T> {
    let httpParams = new HttpParams();
    for (const [cle, valeur] of Object.entries(params)) {
      if (valeur !== undefined && valeur !== null && String(valeur).trim() !== '') {
        httpParams = httpParams.set(cle, String(valeur).trim());
      }
    }
    return this.http.get<ApiResponse<T>>(`${this.apiUrl}/${chemin}`, { params: httpParams }).pipe(
      map((res) => {
        if (res.status === 'error' || res.data === null) throw new Error(res.error ?? 'Erreur API');
        return res.data;
      }),
    );
  }
}
