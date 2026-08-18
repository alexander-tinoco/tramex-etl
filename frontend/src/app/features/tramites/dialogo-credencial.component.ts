import { Component, computed, inject, input, output, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ApiService } from '../../core/api.service';
import { ConfiguracionRecurso } from '../../models/recursos.model';

/**
 * Dialogo de consulta de la credencial de un cliente.
 *
 * Es la operacion mas sensible de la aplicacion, y la interfaz lo refleja: la
 * contrasena llega oculta, se revela solo bajo peticion explicita y el dialogo
 * muestra el numero de asiento que la consulta dejo en la bitacora, para que
 * quien la hace sepa que ha quedado registrada.
 */
@Component({
  selector: 'app-dialogo-credencial',
  standalone: true,
  template: `
    <div class="modal-fondo" (click)="cerrar.emit()">
      <div class="modal modal-angosto" (click)="$event.stopPropagation()" role="dialog" aria-modal="true">
        <header class="modal-cabecera">
          <h3><i class="fa-solid fa-key"></i> Credencial del cliente</h3>
          <button type="button" class="boton-icono" (click)="cerrar.emit()" aria-label="Cerrar">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </header>

        <div class="modal-cuerpo">
          @if (cargando()) {
            <p class="text-center"><i class="fa-solid fa-spinner fa-spin"></i> Descifrando…</p>
          } @else if (error()) {
            <div class="alerta alerta-error" role="alert">
              <i class="fa-solid fa-triangle-exclamation"></i>
              <span>{{ error() }}</span>
            </div>
          } @else if (sinCredencial()) {
            <p class="text-muted">Este registro no tiene ninguna credencial almacenada.</p>
          } @else {
            <p class="text-muted">{{ recurso().titulo }} · registro #{{ registroId() }}</p>
            <div class="campo-control credencial">
              <input
                [type]="visible() ? 'text' : 'password'"
                [value]="contrasena()"
                readonly
                aria-label="Credencial del cliente"
              />
              <button
                type="button"
                class="boton-icono"
                (click)="alternar()"
                [attr.aria-label]="visible() ? 'Ocultar' : 'Mostrar'"
              >
                <i class="fa-solid" [class.fa-eye]="!visible()" [class.fa-eye-slash]="visible()"></i>
              </button>
              <button type="button" class="boton-icono" (click)="copiar()" aria-label="Copiar">
                <i class="fa-solid" [class.fa-copy]="!copiada()" [class.fa-check]="copiada()"></i>
              </button>
            </div>
            <p class="nota-auditoria">
              <i class="fa-solid fa-clipboard-list"></i>
              Esta consulta quedó registrada en la bitácora de auditoría
              (asiento #{{ auditoriaId() }}).
            </p>
          }
        </div>

        <footer class="modal-pie">
          <button type="button" class="btn-secondary" (click)="cerrar.emit()">Cerrar</button>
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
    // La peticion se lanza al construir el dialogo: abrirlo *es* la accion de
    // consultar, y por tanto lo que se audita.
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
          // El backend distingue "no hay credencial" de "hay un criptograma que
          // no abre"; el segundo caso indica una llave rotada o un respaldo
          // ajeno, y merece un mensaje que lleve a revisarlo.
          this.error.set(
            'La credencial no pudo descifrarse con la llave activa. Avisa a quien administre el sistema.',
          );
        } else {
          this.error.set('No se pudo consultar la credencial.');
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
