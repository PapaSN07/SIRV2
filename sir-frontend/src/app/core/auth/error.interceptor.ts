import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, switchMap, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/change-password', '/auth/logout'];

function isAuthEndpoint(req: HttpRequest<unknown>): boolean {
  return AUTH_ENDPOINTS.some((path) => req.url.includes(path));
}

const STATUS_MESSAGES: Record<number, string> = {
  0: 'Serveur injoignable. Vérifiez votre connexion réseau puis réessayez.',
  400: 'Requête invalide. Vérifiez les informations saisies.',
  403: "Vous n'avez pas les droits pour cette action.",
  404: 'Élément introuvable : il a peut-être été supprimé.',
  409: 'Conflit : les données ont été modifiées entre-temps. Rechargez la page.',
  413: 'Fichier trop volumineux.',
  422: 'Certaines informations sont invalides. Vérifiez le formulaire.',
  429: 'Trop de tentatives. Patientez une minute puis réessayez.',
  502: 'Serveur momentanément indisponible. Réessayez dans quelques instants.',
  503: 'Serveur momentanément indisponible. Réessayez dans quelques instants.',
  504: 'Le serveur met trop de temps à répondre. Réessayez dans quelques instants.',
};

/** Message lisible : texte métier renvoyé par l'API, sinon message selon le code HTTP. */
export function httpErrorMessage(error: HttpErrorResponse): string {
  const body: unknown = error.error;
  if (body && typeof body === 'object') {
    const b = body as { error?: unknown; detail?: unknown };
    if (typeof b.error === 'string' && b.error.trim()) return b.error;
    if (typeof b.detail === 'string' && b.detail.trim()) return b.detail;
    if (b.detail && typeof b.detail === 'object') {
      const inner = (b.detail as { error?: unknown }).error;
      if (typeof inner === 'string' && inner.trim()) return inner;
    }
  }
  if (STATUS_MESSAGES[error.status]) return STATUS_MESSAGES[error.status];
  if (error.status >= 500) {
    return 'Erreur interne du serveur. Réessayez ; si le problème persiste, contactez l’administrateur.';
  }
  return 'Une erreur est survenue. Réessayez.';
}

/** Remplace « Http failure response for … » par un message en français, sans changer l'objet. */
function withReadableMessage(error: HttpErrorResponse): HttpErrorResponse {
  Object.defineProperty(error, 'message', { value: httpErrorMessage(error), configurable: true });
  return error;
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
      return throwError(() => (error instanceof HttpErrorResponse ? withReadableMessage(error) : error));
    }),
  );
};
