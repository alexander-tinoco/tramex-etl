import { Component, computed, inject, input, output, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ApiService } from '../../core/api.service';
import { ConfiguracionRecurso } from '../../models/recursos.model';
import { PictogramaComponent } from '../../shared/pictograma.component';

/**
 * Dialog for viewing a client's credential.
 *
 * It's the most sensitive operation in the system, and the only gold piece
 * anywhere in the interface: the logo's gold is reserved for this, so
 * whenever it appears it always means the same thing.
 *
 * The credential arrives hidden, is revealed only on explicit request, and
 * the dialog shows the audit-log entry the lookup just left behind. Letting
 * whoever queries it see that entry is part of the design: the system's
 * promise is that access leaves a trace, and a promise that isn't visible
 * reassures no one.
 */
@Component({
  selector: 'app-dialogo-credencial',
  standalone: true,
  imports: [PictogramaComponent],
  template: `
    <div class="telon" (click)="cerrar.emit()">
      <div
        class="ventanilla angosta"
        (click)="$event.stopPropagation()"
        role="dialog"
        aria-modal="true"
        aria-labelledby="titulo-credencial"
      >
        <header class="ventanilla-cabecera">
          <h3 id="titulo-credencial">
            <app-picto nombre="llave" [tamano]="18" />
            Client credential
          </h3>
          <button type="button" class="boton-icono" (click)="cerrar.emit()" aria-label="Close">
            <app-picto nombre="cerrar" [tamano]="16" />
          </button>
        </header>

        <div class="ventanilla-cuerpo">
          @if (cargando()) {
            <p class="medio">Decrypting…</p>
          } @else if (error()) {
            <div class="aviso error" role="alert">
              <app-picto nombre="alerta" [tamano]="18" />
              <span>{{ error() }}</span>
            </div>
          } @else if (sinCredencial()) {
            <div class="aviso dato">
              <app-picto nombre="aviso" [tamano]="18" />
              <span>This record has no credential stored.</span>
            </div>
          } @else {
            <div class="placa-credencial">
              <p class="procedencia">{{ recurso().titulo }} · record {{ registroId() }}</p>
              <div class="valor">
                <input
                  [type]="visible() ? 'text' : 'password'"
                  [value]="contrasena()"
                  readonly
                  aria-label="Client credential"
                />
                <button
                  type="button"
                  class="boton-icono"
                  (click)="alternar()"
                  [attr.aria-label]="visible() ? 'Hide' : 'Show'"
                >
                  <app-picto [nombre]="visible() ? 'ocultar' : 'ver'" [tamano]="17" />
                </button>
                <button
                  type="button"
                  class="boton-icono"
                  (click)="copiar()"
                  [attr.aria-label]="copiada() ? 'Copied' : 'Copy credential'"
                >
                  <app-picto [nombre]="copiada() ? 'confirmado' : 'copiar'" [tamano]="17" />
                </button>
              </div>
            </div>

            <p class="folio-auditoria">
              <app-picto nombre="bitacora" [tamano]="16" />
              <span>
                This lookup was logged in the audit trail with your user and the date.
                Entry number: <strong>{{ auditoriaId() }}</strong>
              </span>
            </p>
          }
        </div>

        <footer class="ventanilla-pie">
          <button type="button" class="boton secundario" (click)="cerrar.emit()">Close</button>
        </footer>
      </div>
    </div>
  `,
})
export class DialogoCredencialComponent {
  private readonly api = inject(ApiService);

  readonly recurso = input.required<ConfiguracionRecurso>();
  readonly registroId = input.required<number>();
  readonly cerrar = output<void>();

  readonly cargando = signal(true);
  readonly error = signal('');
  readonly contrasena = signal<string | null>(null);
  readonly auditoriaId = signal<number | null>(null);
  readonly visible = signal(false);
  readonly copiada = signal(false);

  readonly sinCredencial = computed(
    () => !this.cargando() && !this.error() && this.contrasena() === null,
  );

  constructor() {
    // The request fires as soon as the dialog is constructed: opening it *is*
    // the act of looking it up, and therefore what gets audited.
    queueMicrotask(() => this.consultar());
  }

  private consultar(): void {
    this.api.obtenerCredencial(this.recurso().endpoint, this.registroId()).subscribe({
      next: (respuesta) => {
        this.contrasena.set(respuesta.contrasena);
        this.auditoriaId.set(respuesta.auditoria_id);
        this.cargando.set(false);
      },
      error: (fallo: unknown) => {
        this.cargando.set(false);
        if (fallo instanceof HttpErrorResponse && fallo.status === 500) {
          // The backend distinguishes "there is no credential" from "there is
          // a ciphertext that won't open"; the second case points to a
          // rotated key or a foreign backup, and deserves a message that
          // leads to checking it.
          this.error.set(
            'The credential could not be decrypted with the active key. Notify whoever administers the system.',
          );
        } else {
          this.error.set('Could not retrieve the credential.');
        }
      },
    });
  }

  alternar(): void {
    this.visible.update((valor) => !valor);
  }

  copiar(): void {
    const valor = this.contrasena();
    if (!valor) {
      return;
    }
    void navigator.clipboard.writeText(valor).then(() => {
      this.copiada.set(true);
      setTimeout(() => this.copiada.set(false), 2000);
    });
  }
}
