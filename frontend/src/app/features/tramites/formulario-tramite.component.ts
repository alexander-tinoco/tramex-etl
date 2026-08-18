import { Component, computed, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CuerpoTramite, Tramite } from '../../models/api.model';
import { ConfiguracionRecurso } from '../../models/recursos.model';

/**
 * Formulario de alta y edicion, generado a partir de la configuracion del
 * recurso.
 *
 * No hay una plantilla por recurso: los campos, sus etiquetas y su tipo salen
 * de `RECURSOS`, de modo que anadir una columna es tocar un archivo y no cuatro
 * bloques de HTML.
 */
@Component({
  selector: 'app-formulario-tramite',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './formulario-tramite.component.html',
})
export class FormularioTramiteComponent {
  readonly recurso = input.required<ConfiguracionRecurso>();
  /** Registro a editar, o `null` para un alta. */
  readonly registro = input<Tramite | null>(null);
  readonly guardando = input<boolean>(false);
  readonly error = input<string>('');

  readonly guardar = output<CuerpoTramite>();
  readonly cerrar = output<void>();

  readonly valores = signal<Record<string, string>>({});
  readonly esEdicion = computed(() => this.registro() !== null);

  constructor() {
    // Se rellena en el microtask siguiente para que las entradas ya esten
    // resueltas cuando se lea el registro.
    queueMicrotask(() => this.precargar());
  }

  private precargar(): void {
    const actual = this.registro();
    const iniciales: Record<string, string> = {};
    for (const campo of this.recurso().campos) {
      // Las credenciales nunca se precargan: la API no las devuelve en las
      // lecturas, y dejar el campo vacio comunica lo correcto (solo se
      // sobrescribe si se escribe algo).
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
        // Un campo de contrasena vacio significa "no la cambies". Enviar null
        // borraria la credencial del cliente sin que nadie lo pidiera.
        if (valor) {
          cuerpo[campo.nombre] = valor;
        }
        continue;
      }

      // En edicion, un campo vaciado a proposito se envia como null para que
      // la API lo borre; en un alta simplemente se omite.
      if (valor) {
        cuerpo[campo.nombre] = valor;
      } else if (this.esEdicion()) {
        cuerpo[campo.nombre] = null;
      }
    }

    this.guardar.emit(cuerpo);
  }
}
