import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, map, of, shareReplay, switchMap, tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api.models';
import { LoginRequest, MeResponse, TokenResponse, ChangePasswordRequest } from '../../shared/models/auth.models';

const TOKEN_KEY = 'sir_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly currentUser = signal<MeResponse | null>(null);

  /** Renouvellement en cours, partagé par toutes les requêtes tombées en 401 en même temps. */
  private refreshInFlight$: Observable<string> | null = null;

  constructor(
    private readonly http: HttpClient,
    private readonly router: Router,
  ) {}

  signIn(credentials: LoginRequest): Observable<MeResponse> {
    return this.http
      .post<ApiResponse<TokenResponse>>(`${environment.apiUrl}/auth/login`, credentials, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => sessionStorage.setItem(TOKEN_KEY, this.unwrap(res).access_token)),
        switchMap(() => this.fetchMe()),
      );
  }

  changePassword(body: ChangePasswordRequest): Observable<MeResponse> {
    return this.http
      .post<ApiResponse<TokenResponse>>(`${environment.apiUrl}/auth/change-password`, body, {
        withCredentials: true,
      })
      .pipe(
        tap((res) => sessionStorage.setItem(TOKEN_KEY, this.unwrap(res).access_token)),
        switchMap(() => this.fetchMe()),
      );
  }

  fetchMe(): Observable<MeResponse> {
    return this.http.get<ApiResponse<MeResponse>>(`${environment.apiUrl}/auth/me`).pipe(
      map((res) => this.unwrap(res)),
      tap((user) => this.currentUser.set(user)),
    );
  }

  logout(): Observable<void> {
    return this.http
      .delete<void>(`${environment.apiUrl}/auth/logout`, { withCredentials: true })
      .pipe(
        // Session déjà expirée côté serveur : on déconnecte quand même le navigateur.
        catchError(() => of(undefined)),
        finalize(() => {
          this.clearSession();
          void this.router.navigate(['/login']);
        }),
      );
  }

  /**
   * Obtient un nouvel access token via le cookie HttpOnly refresh_token.
   * Plusieurs appels simultanés partagent une seule requête au serveur.
   */
  refreshAccessToken(): Observable<string> {
    if (!this.refreshInFlight$) {
      this.refreshInFlight$ = this.http
        .post<ApiResponse<TokenResponse>>(`${environment.apiUrl}/auth/refresh`, {}, { withCredentials: true })
        .pipe(
          map((res) => this.unwrap(res).access_token),
          tap((token) => sessionStorage.setItem(TOKEN_KEY, token)),
          finalize(() => (this.refreshInFlight$ = null)),
          shareReplay(1),
        );
    }
    return this.refreshInFlight$;
  }

  /** Fin de session côté navigateur (sans appel serveur) : jeton et profil effacés. */
  clearSession(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    this.currentUser.set(null);
  }

  getAccessToken(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  isAuthenticated(): boolean {
    return this.getAccessToken() !== null;
  }

  hasRole(...roles: string[]): boolean {
    const user = this.currentUser();
    if (!user?.role_label) return false;
    if (user.role_label === 'SUPERADMIN') return true;
    return roles.includes(user.role_label);
  }

  /** Rôle réel du compte, sans le passe-droit SUPERADMIN. Sert au périmètre (région). */
  isExactRole(...roles: string[]): boolean {
    const label = this.currentUser()?.role_label;
    return label !== null && label !== undefined && roles.includes(label);
  }

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
