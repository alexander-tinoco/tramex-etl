import { Component, input, output } from '@angular/core';
import { NombrePictograma, PictogramaComponent } from './pictograma.component';

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
  imports: [PictogramaComponent],
  template: `
    <div class="telon" (click)="cancelar.emit()">
      <div
        class="ventanilla angosta"
        (click)="$event.stopPropagation()"
        role="dialog"
        aria-modal="true"
      >
        <header class="ventanilla-cabecera">
          <h3>
            <app-picto [nombre]="picto()" [tamano]="18" />
            {{ titulo() }}
          </h3>
        </header>
        <div class="ventanilla-cuerpo">
          <p>{{ mensaje() }}</p>
          @if (detalle()) {
            <p class="medio prosa" style="margin-top: 0.5rem">{{ detalle() }}</p>
          }
        </div>
        <footer class="ventanilla-pie">
          <button type="button" class="boton secundario" (click)="cancelar.emit()">Cancelar</button>
          <button
            type="button"
            [class]="peligroso() ? 'boton peligro' : 'boton'"
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
  readonly picto = input<NombrePictograma>('aviso');
  readonly peligroso = input<boolean>(false);

  readonly confirmar = output<void>();
  readonly cancelar = output<void>();
}
