import { Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CuerpoTramite, Tramite } from '../../models/api.model';
import { ConfiguracionRecurso } from '../../models/recursos.model';
import { PictogramaComponent } from '../../shared/pictograma.component';

/**
 * Create/edit form, generated from the resource's configuration.
 *
 * There is no per-resource template: the fields, their labels and their type
 * come from `RECURSOS`, so adding a column means touching one file, not four
 * blocks of HTML.
 */
@Component({
  selector: 'app-formulario-tramite',
  standalone: true,
  imports: [FormsModule, PictogramaComponent],
  templateUrl: './formulario-tramite.component.html',
})
export class FormularioTramiteComponent {
  readonly recurso = input.required<ConfiguracionRecurso>();
  /** Record being edited, or `null` for a new one. */
  readonly registro = input<Tramite | null>(null);
  readonly guardando = input<boolean>(false);
  readonly error = input<string>('');

  readonly guardar = output<CuerpoTramite>();
  readonly cerrar = output<void>();

  readonly valores = signal<Record<string, string>>({});
  readonly esEdicion = computed(() => this.registro() !== null);

  constructor() {
    // Filled in on the next microtask so the inputs are already resolved by
    // the time the record is read.
    queueMicrotask(() => this.precargar());
  }

  private precargar(): void {
    const actual = this.registro();
    const iniciales: Record<string, string> = {};
    for (const campo of this.recurso().campos) {
      // Credentials are never preloaded: the API doesn't return them on
      // reads, and leaving the field blank communicates the right thing (it
      // is only overwritten if something is typed).
      if (campo.tipo === 'password' || !actual) {
        iniciales[campo.nombre] = '';
        continue;
      }
      const valor = (actual as unknown as Record<string, unknown>)[campo.nombre];
      iniciales[campo.nombre] = valor === null || valor === undefined ? '' : String(valor);
    }
    this.valores.set(iniciales);
  }

  actualizarCampo(nombre: string, valor: string): void {
    this.valores.update((actuales) => ({ ...actuales, [nombre]: valor }));
  }

  enviar(evento: Event): void {
    evento.preventDefault();
    if (this.guardando()) {
      return;
    }

    const cuerpo: CuerpoTramite = {};
    const actuales = this.valores();

    for (const campo of this.recurso().campos) {
      const valor = (actuales[campo.nombre] ?? '').trim();

      if (campo.tipo === 'password') {
        // An empty password field means "don't change it". Sending null
        // would delete the client's credential without anyone asking for it.
        if (valor) {
          cuerpo[campo.nombre] = valor;
        }
        continue;
      }

      // In edit mode, a field cleared on purpose is sent as null so the API
      // deletes it; on create it's simply omitted.
      if (valor) {
        cuerpo[campo.nombre] = valor;
      } else if (this.esEdicion()) {
        cuerpo[campo.nombre] = null;
      }
    }

    this.guardar.emit(cuerpo);
  }
}
