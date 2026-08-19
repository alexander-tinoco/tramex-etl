import { Component, input, output } from '@angular/core';
import { NombrePictograma, PictogramaComponent } from './pictograma.component';

/**
 * Reusable confirmation dialog.
 *
 * Exists as its own component because the dashboard needed three nearly
 * identical dialogs (archive, restore, confirm sign-out) and all three were
 * hand-written inline in the same template.
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
          <button type="button" class="boton secundario" (click)="cancelar.emit()">Cancel</button>
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
  readonly textoConfirmar = input<string>('Confirm');
  readonly picto = input<NombrePictograma>('aviso');
  readonly peligroso = input<boolean>(false);

  readonly confirmar = output<void>();
  readonly cancelar = output<void>();
}
