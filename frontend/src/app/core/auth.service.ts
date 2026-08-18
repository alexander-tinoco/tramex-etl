import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { RespuestaToken, Usuario } from '../models/api.model';

/**
 * Estado de sesion de la aplicacion.
 *
 * La sesion vive en una cookie `httpOnly` emitida por la API, no en
 * `localStorage`. El cambio importa: el token guardado en `localStorage` era
 * legible por cualquier script de la pagina, de modo que un XSS bastaba para
 * robar la sesion. Una cookie `httpOnly` es invisible para JavaScript.
 *
 * La consecuencia de diseno es que el frontend **no puede leer la sesion**: la
 * unica forma de saber si hay una activa es preguntarle a la API. De ahi
 * `cargarSesion()`, que se ejecuta al arrancar la aplicacion.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  private readonly _usuario = signal<Usuario | null>(null);
  private readonly _sesionResuelta = signal(false);

  /** Usuario de la sesion actual, o `null` si no hay ninguna. */
  readonly usuario = this._usuario.asReadonly();

  /** `false` mientras aun no se sabe si hay sesion; evita parpadeos al arrancar. */
  readonly sesionResuelta = this._sesionResuelta.asReadonly();

  readonly estaAutenticado = computed(() => this._usuario() !== null);
  readonly esAdmin = computed(() => this._usuario()?.rol === 'admin');
  readonly nombreVisible = computed(() => this._usuario()?.nombre ?? 'Invitado');

  /**
   * Autentica contra la API.
   *
   * El cuerpo va como formulario porque el endpoint sigue el flujo estandar de
   * OAuth2 "password", que es tambien lo que espera el "Authorize" de Swagger.
   */
  iniciarSesion(correo: string, contrasena: string): Observable<RespuestaToken> {
    const cuerpo = new URLSearchParams();
    cuerpo.set('username', correo);
    cuerpo.set('password', contrasena);

    return this.http
      .post<RespuestaToken>(`${this.baseUrl}/auth/token`, cuerpo.toString(), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        withCredentials: true,
      })
      .pipe(
        tap((respuesta) => {
          // El token del cuerpo se ignora a proposito: la sesion la lleva la
          // cookie. Guardarlo aqui reintroduciria el problema que se acaba de
          // resolver.
          this._usuario.set(respuesta.usuario);
          this._sesionResuelta.set(true);
        }),
      );
  }

  cerrarSesion(): Observable<void> {
    return this.http
      .post<void>(`${this.baseUrl}/auth/logout`, {}, { withCredentials: true })
      .pipe(tap(() => this.limpiar()));
  }

  /**
   * Pregunta a la API por la sesion vigente.
   *
   * Se llama al arrancar la aplicacion: como la cookie es `httpOnly`, es la
   * unica forma de recuperar el estado tras recargar la pagina.
   */
  cargarSesion(): Observable<Usuario> {
    return this.http
      .get<Usuario>(`${this.baseUrl}/auth/me`, { withCredentials: true })
      .pipe(
        tap({
          next: (usuario) => {
            this._usuario.set(usuario);
            this._sesionResuelta.set(true);
          },
          error: () => this.limpiar(),
        }),
      );
  }

  cambiarContrasena(actual: string, nueva: string): Observable<void> {
    return this.http.post<void>(
      `${this.baseUrl}/auth/cambiar-contrasena`,
      { contrasena_actual: actual, contrasena_nueva: nueva },
      { withCredentials: true },
    );
  }

  /** Descarta el estado local. La cookie la invalida la API. */
  limpiar(): void {
    this._usuario.set(null);
    this._sesionResuelta.set(true);
  }
}
