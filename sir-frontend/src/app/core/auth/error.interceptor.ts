import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const auth = inject(AuthService);

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      if (error.status === 401 && !req.url.includes('/auth/login')) {
        sessionStorage.removeItem('sir_access_token');
        auth.currentUser.set(null);
        void router.navigate(['/login']);
      } else if (
        error.status === 403 &&
        !req.url.includes('/auth/login') &&
        !req.url.includes('/auth/change-password')
      ) {
        void router.navigate(['/acces-refuse']);
      }

      return throwError(() => error);
    }),
  );
};
