import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { RespuestaToken, Usuario } from '../models/api.model';

/**
 * Application session state.
 *
 * The session lives in an `httpOnly` cookie issued by the API, not in
 * `localStorage`. The change matters: a token stored in `localStorage` was
 * readable by any script on the page, so an XSS was enough to steal the
 * session. An `httpOnly` cookie is invisible to JavaScript.
 *
 * The design consequence is that the frontend **cannot read the session**:
 * the only way to know if one is active is to ask the API. Hence
 * `cargarSesion()`, which runs when the application starts.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  private readonly _usuario = signal<Usuario | null>(null);
  private readonly _sesionResuelta = signal(false);

  /** User of the current session, or `null` if there isn't one. */
  readonly usuario = this._usuario.asReadonly();

  /** `false` while it isn't yet known whether there's a session; avoids a flash on startup. */
  readonly sesionResuelta = this._sesionResuelta.asReadonly();

  readonly estaAutenticado = computed(() => this._usuario() !== null);
  readonly esAdmin = computed(() => this._usuario()?.rol === 'admin');
  readonly nombreVisible = computed(() => this._usuario()?.nombre ?? 'Guest');

  /**
   * Authenticates against the API.
   *
   * The body is sent as a form because the endpoint follows the standard
   * OAuth2 "password" flow, which is also what Swagger's "Authorize" expects.
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
          // The token in the body is deliberately ignored: the cookie carries
          // the session. Storing it here would reintroduce the problem that
          // was just solved.
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
   * Asks the API for the current session.
   *
   * Called when the application starts: since the cookie is `httpOnly`, this
   * is the only way to recover the state after reloading the page.
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

  /** Discards local state. The API is what invalidates the cookie. */
  limpiar(): void {
    this._usuario.set(null);
    this._sesionResuelta.set(true);
  }
}
