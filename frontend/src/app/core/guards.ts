import { inject } from '@angular/core';
import { CanActivateFn, Router, UrlTree } from '@angular/router';
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

/**
 * Exige rol de administrador.
 *
 * Tiene que resolver la sesion por su cuenta, igual que `authGuard`. Angular
 * evalua los guards de una misma ruta **en paralelo**, no en cadena: al entrar
 * por enlace directo o recargar la pagina, este guard se ejecutaba antes de que
 * `authGuard` terminara de preguntar a la API y veia siempre "sin sesion", de
 * modo que rebotaba al panel incluso a una administradora legitima.
 *
 * Es solo una comodidad de la interfaz: la API vuelve a comprobar el rol en
 * cada peticion, que es donde realmente se protegen los datos.
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
