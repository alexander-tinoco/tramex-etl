import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../core/auth.service';
import { PictogramaComponent } from '../../shared/pictograma.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, PictogramaComponent],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);

  correo = '';
  contrasena = '';

  readonly mostrarContrasena = signal(false);
  readonly cargando = signal(false);
  readonly error = signal('');

  /** The interceptor redirects here with this flag when the session expires. */
  readonly sesionExpirada = signal(this.ruta.snapshot.queryParamMap.get('expirada') === 'true');

  alternarVisibilidad(): void {
    this.mostrarContrasena.update((valor) => !valor);
  }

  enviar(evento: Event): void {
    evento.preventDefault();
    if (!this.correo || !this.contrasena || this.cargando()) {
      return;
    }

    this.cargando.set(true);
    this.error.set('');
    this.sesionExpirada.set(false);

    this.auth.iniciarSesion(this.correo, this.contrasena).subscribe({
      next: () => {
        this.cargando.set(false);
        void this.router.navigate(['/dashboard']);
      },
      error: (fallo: unknown) => {
        this.cargando.set(false);
        this.error.set(this.describirError(fallo));
      },
    });
  }

  /**
   * Translates the failure into a useful message.
   *
   * 429 is deliberately distinguished from 401: if the account was locked
   * out from failed attempts, saying "incorrect credentials" would make the
   * person keep trying passwords without understanding why they can't get in.
   */
  private describirError(fallo: unknown): string {
    if (!(fallo instanceof HttpErrorResponse)) {
      return 'Could not sign in.';
    }
    switch (fallo.status) {
      case 401:
        return 'Incorrect email or password.';
      case 429:
        return typeof fallo.error?.detail === 'string'
          ? fallo.error.detail
          : 'Too many attempts. Wait a few minutes before trying again.';
      case 0:
        return 'No connection to the server.';
      default:
        return 'An unexpected error occurred. Try again.';
    }
  }
}
