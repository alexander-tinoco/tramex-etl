import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../core/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
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

  /** El interceptor redirige aqui con esta marca cuando la sesion caduca. */
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
   * Traduce el fallo a un mensaje util.
   *
   * El 429 se distingue del 401 a proposito: si la cuenta quedo bloqueada por
   * intentos fallidos, decir "credenciales incorrectas" haria que la persona
   * siguiera probando contrasenas sin entender por que no entra.
   */
  private describirError(fallo: unknown): string {
    if (!(fallo instanceof HttpErrorResponse)) {
      return 'No se pudo completar el inicio de sesión.';
    }
    switch (fallo.status) {
      case 401:
        return 'Correo o contraseña incorrectos.';
      case 429:
        return typeof fallo.error?.detail === 'string'
          ? fallo.error.detail
          : 'Demasiados intentos. Espera unos minutos antes de volver a intentar.';
      case 0:
        return 'No hay conexión con el servidor.';
      default:
        return 'Ocurrió un error inesperado. Intenta de nuevo.';
    }
  }
}
