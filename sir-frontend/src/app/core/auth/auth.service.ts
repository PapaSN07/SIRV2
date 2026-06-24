import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, switchMap, tap, map } from 'rxjs';
import { environment } from '../../../environments/environment';
import { ApiResponse } from '../../shared/models/api.models';
import { LoginRequest, MeResponse, TokenResponse, ChangePasswordRequest } from '../../shared/models/auth.models';

const TOKEN_KEY = 'sir_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly currentUser = signal<MeResponse | null>(null);

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
        tap(() => {
          sessionStorage.removeItem(TOKEN_KEY);
          this.currentUser.set(null);
          void this.router.navigate(['/login']);
        }),
      );
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

  private unwrap<T>(res: ApiResponse<T>): T {
    if (res.status === 'error' || res.data === null) {
      throw new Error(res.error ?? 'Erreur API');
    }
    return res.data;
  }
}
