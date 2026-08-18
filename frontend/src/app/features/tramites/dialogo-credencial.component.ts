import { Component, computed, inject, input, output, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ApiService } from '../../core/api.service';
import { ConfiguracionRecurso } from '../../models/recursos.model';
import { PictogramaComponent } from '../../shared/pictograma.component';

/**
 * Diálogo de consulta de la credencial de un cliente.
 *
 * Es la operación más sensible del sistema, y la única pieza dorada de toda la
 * interfaz: el dorado del logotipo está reservado a esto, así que cuando
 * aparece significa siempre lo mismo.
 *
 * La credencial llega oculta, se revela solo bajo petición explícita, y el
 * diálogo muestra el folio del asiento que la consulta acaba de dejar en la
 * bitácora. Que quien consulta vea ese folio es parte del diseño: la promesa
 * del sistema es que el acceso deja huella, y una promesa que no se ve no
 * tranquiliza a nadie.
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
            Credencial del cliente
          </h3>
          <button type="button" class="boton-icono" (click)="cerrar.emit()" aria-label="Cerrar">
            <app-picto nombre="cerrar" [tamano]="16" />
          </button>
        </header>

        <div class="ventanilla-cuerpo">
          @if (cargando()) {
            <p class="medio">Descifrando…</p>
          } @else if (error()) {
            <div class="aviso error" role="alert">
              <app-picto nombre="alerta" [tamano]="18" />
              <span>{{ error() }}</span>
            </div>
          } @else if (sinCredencial()) {
            <div class="aviso dato">
              <app-picto nombre="aviso" [tamano]="18" />
              <span>Este registro no tiene ninguna credencial almacenada.</span>
            </div>
          } @else {
            <div class="placa-credencial">
              <p class="procedencia">{{ recurso().titulo }} · registro {{ registroId() }}</p>
              <div class="valor">
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
                  <app-picto [nombre]="visible() ? 'ocultar' : 'ver'" [tamano]="17" />
                </button>
                <button
                  type="button"
                  class="boton-icono"
                  (click)="copiar()"
                  [attr.aria-label]="copiada() ? 'Copiada' : 'Copiar credencial'"
                >
                  <app-picto [nombre]="copiada() ? 'confirmado' : 'copiar'" [tamano]="17" />
                </button>
              </div>
            </div>

            <p class="folio-auditoria">
              <app-picto nombre="bitacora" [tamano]="16" />
              <span>
                Esta consulta quedó asentada en la bitácora con tu usuario y la fecha.
                Folio del asiento: <strong>{{ auditoriaId() }}</strong>
              </span>
            </p>
          }
        </div>

        <footer class="ventanilla-pie">
          <button type="button" class="boton secundario" (click)="cerrar.emit()">Cerrar</button>
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
    // La petición se lanza al construir el diálogo: abrirlo *es* la acción de
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
          // El backend distingue «no hay credencial» de «hay un criptograma que
          // no abre»; el segundo caso indica una llave rotada o un respaldo
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
