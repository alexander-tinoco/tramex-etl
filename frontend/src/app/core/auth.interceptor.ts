import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Session interceptor.
 *
 * It no longer attaches any token: the session travels in an `httpOnly`
 * cookie that the browser sends on its own. All that's left to do here is
 * make sure requests include it and react when the API rejects it.
 */
export const authInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // `withCredentials` is set here as a safety net: it only takes one request
  // forgetting the option for the API to see it as anonymous.
  const conCredenciales = peticion.clone({ withCredentials: true });

  return siguiente(conCredenciales).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        auth.limpiar();
        // `/auth/me` normally responds 401 on startup with no session; in
        // that case there's nothing to interrupt and redirecting would be
        // annoying.
        if (!peticion.url.endsWith('/auth/me') && router.url !== '/login') {
          void router.navigate(['/login'], { queryParams: { expirada: 'true' } });
        }
      }
      return throwError(() => error);
    }),
  );
};
