import { inject } from '@angular/core';
import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Interceptor de sesion.
 *
 * Ya no adjunta ningun token: la sesion viaja en una cookie `httpOnly` que el
 * navegador envia por su cuenta. Lo unico que queda por hacer aqui es asegurar
 * que las peticiones la incluyan y reaccionar cuando la API la rechaza.
 */
export const authInterceptor: HttpInterceptorFn = (peticion, siguiente) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  // `withCredentials` se fija aqui como red de seguridad: basta con que una
  // peticion olvide la opcion para que la API la vea como anonima.
  const conCredenciales = peticion.clone({ withCredentials: true });

  return siguiente(conCredenciales).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        auth.limpiar();
        // `/auth/me` responde 401 de forma normal al arrancar sin sesion; en ese
        // caso no hay nada que interrumpir y redirigir seria molesto.
        if (!peticion.url.endsWith('/auth/me') && router.url !== '/login') {
          void router.navigate(['/login'], { queryParams: { expirada: 'true' } });
        }
      }
      return throwError(() => error);
    }),
  );
};
