import { Component, input, output } from '@angular/core';

/**
 * Dialogo de confirmacion reutilizable.
 *
 * Existe como componente propio porque el dashboard necesitaba tres dialogos
 * casi identicos (archivar, restaurar, confirmar salida) y los tres estaban
 * escritos a mano en la misma plantilla.
 */
@Component({
  selector: 'app-dialogo-confirmacion',
  standalone: true,
  template: `
    <div class="modal-fondo" (click)="cancelar.emit()">
      <div class="modal modal-angosto" (click)="$event.stopPropagation()" role="dialog" aria-modal="true">
        <header class="modal-cabecera">
          <h3><i class="fa-solid" [class]="icono()"></i> {{ titulo() }}</h3>
        </header>
        <div class="modal-cuerpo">
          <p>{{ mensaje() }}</p>
          @if (detalle()) {
            <p class="text-muted">{{ detalle() }}</p>
          }
        </div>
        <footer class="modal-pie">
          <button type="button" class="btn-secondary" (click)="cancelar.emit()">Cancelar</button>
          <button
            type="button"
            [class]="peligroso() ? 'btn-danger' : 'btn-primary'"
            (click)="confirmar.emit()"
          >
            {{ textoConfirmar() }}
          </button>
        </footer>
      </div>
    </div>
  `,
})
export class DialogoConfirmacionComponent {
  readonly titulo = input.required<string>();
  readonly mensaje = input.required<string>();
  readonly detalle = input<string>('');
  readonly textoConfirmar = input<string>('Confirmar');
  readonly icono = input<string>('fa-circle-question');
  readonly peligroso = input<boolean>(false);

  readonly confirmar = output<void>();
  readonly cancelar = output<void>();
}
