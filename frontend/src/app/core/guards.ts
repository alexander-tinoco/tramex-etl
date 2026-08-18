import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { AuthService } from './auth.service';

/**
 * Exige sesion iniciada.
 *
 * Como la cookie es `httpOnly`, el guard no puede inspeccionarla: si el estado
 * aun no se ha resuelto (recarga de pagina, enlace directo), pregunta a la API.
 * Esta comprobacion no sustituye a la del servidor, que es la que realmente
 * protege los datos; aqui solo se evita mostrar una pantalla que fallaria.
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

/** Exige rol de administrador. La API lo vuelve a verificar en cada peticion. */
export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.esAdmin() ? true : router.createUrlTree(['/dashboard']);
};
