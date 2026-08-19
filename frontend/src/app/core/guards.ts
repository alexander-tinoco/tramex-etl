import { inject } from '@angular/core';
import { CanActivateFn, Router, UrlTree } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Requires a signed-in session.
 *
 * Since the cookie is `httpOnly`, the guard can't inspect it: if the state
 * hasn't been resolved yet (page reload, direct link), it asks the API. This
 * check doesn't replace the server's, which is what actually protects the
 * data; here it only avoids showing a screen that would fail.
 */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.estaAutenticado()) {
    return true;
  }

  return auth.cargarSesion().pipe(
    map(() => true),
    catchError(() => of(router.createUrlTree(['/login']))),
  );
};

/**
 * Requires the administrator role.
 *
 * It has to resolve the session on its own, just like `authGuard`. Angular
 * evaluates the guards of a single route **in parallel**, not in a chain:
 * entering via a direct link or reloading the page used to run this guard
 * before `authGuard` finished asking the API, so it always saw "no session"
 * and bounced even a legitimate administrator back to the panel.
 *
 * It's only a convenience for the interface: the API checks the role again
 * on every request, which is where the data is actually protected.
 */
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const alPanel = (): UrlTree => router.createUrlTree(['/dashboard']);

  if (auth.sesionResuelta()) {
    return auth.esAdmin() ? true : alPanel();
  }

  return auth.cargarSesion().pipe(
    map((usuario) => (usuario.rol === 'admin' ? true : alPanel())),
    catchError(() => of(router.createUrlTree(['/login']))),
  );
};
