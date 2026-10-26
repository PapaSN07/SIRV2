import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/change-password', '/auth/logout'];

function isAuthEndpoint(req: HttpRequest<unknown>): boolean {
  return AUTH_ENDPOINTS.some((path) => req.url.includes(path));
}

/**
 * 401 : on tente une fois de renouveler la session (cookie refresh) puis on rejoue
 * la requête ; l'utilisateur ne perd ni sa page ni sa saisie. Si le renouvellement
 * échoue, retour à la connexion avec l'adresse courante pour y revenir ensuite.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthService);

  const goToLogin = () => {
    auth.clearSession();
    const returnUrl = router.url && !router.url.startsWith('/login') ? router.url : undefined;
    void router.navigate(['/login'], { queryParams: returnUrl ? { returnUrl } : {} });
  };

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !isAuthEndpoint(req)) {
        return auth.refreshAccessToken().pipe(
          switchMap((token) =>
            next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` }, withCredentials: true })),
          ),
          catchError((refreshError: unknown) => {
            goToLogin();
            return throwError(() => refreshError);
          }),
        );
      }
      if (error.status === 403 && !isAuthEndpoint(req)) {
        void router.navigate(['/acces-refuse']);
      }
      return throwError(() => error);
    }),
  );
};
