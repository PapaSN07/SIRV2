import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }

  return router.createUrlTree(['/login'], {
    queryParams: state.url && state.url !== '/' ? { returnUrl: state.url } : {},
  });
};

export const premiereConnexionGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isAuthenticated()) {
    return true;
  }

  const user = auth.currentUser();
  if (user) {
    if (user.premiere_connexion) {
      return router.createUrlTree(['/changer-mot-de-passe'], {
        queryParams: { login: user.login },
      });
    }
    return true;
  }

  return auth.fetchMe().pipe(
    map((fetched) => {
      if (fetched.premiere_connexion) {
        return router.createUrlTree(['/changer-mot-de-passe'], {
          queryParams: { login: fetched.login },
        });
      }
      return true;
    }),
  );
};

export const roleGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const roles = (route.data['roles'] as string[]) ?? [];

  if (!auth.isAuthenticated()) {
    return router.createUrlTree(['/login']);
  }

  if (roles.length === 0 || auth.hasRole(...roles)) {
    return true;
  }

  return router.createUrlTree(['/acces-refuse']);
};
