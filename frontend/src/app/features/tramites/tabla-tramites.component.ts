import { Component, OnChanges, OnDestroy, computed, inject, input, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Subject, debounceTime, distinctUntilChanged, takeUntil } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { CuerpoTramite, Tramite } from '../../models/api.model';
import { ConfiguracionRecurso } from '../../models/recursos.model';
import { formatearValor } from '../../shared/formato';
import { DialogoConfirmacionComponent } from '../../shared/dialogo-confirmacion.component';
import { DialogoCredencialComponent } from './dialogo-credencial.component';
import { FormularioTramiteComponent } from './formulario-tramite.component';
import { PictogramaComponent } from '../../shared/pictograma.component';

const TAMANO_PAGINA = 10;

/** Columnas cuyo contenido se teclea después en un portal consular. */
const CAMPOS_DE_DATO = new Set([
  'id',
  'id_solicitud',
  'telefono',
  'numero_pasaporte',
  'correo_electronico',
  'cuenta_ircc',
  'fecha_cita',
  'cargado_en',
  'actualizado_en',
]);

/**
 * Tabla de un recurso de tramite, con busqueda, paginacion y acciones.
 *
 * Es el mismo componente para los cuatro recursos: la diferencia entra por la
 * configuracion. En la version anterior toda esta logica vivia dentro de un
 * unico componente de 378 lineas que ademas gestionaba la navegacion, el
 * resumen y tres modales.
 */
@Component({
  selector: 'app-tabla-tramites',
  standalone: true,
  imports: [
    FormularioTramiteComponent,
    DialogoCredencialComponent,
    DialogoConfirmacionComponent,
    PictogramaComponent,
  ],
  templateUrl: './tabla-tramites.component.html',
})
export class TablaTramitesComponent implements OnChanges, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly destruido = new Subject<void>();
  private readonly terminoBuscado = new Subject<string>();

  readonly recurso = input.required<ConfiguracionRecurso>();

  readonly registros = signal<Tramite[]>([]);
  readonly total = signal(0);
  readonly pagina = signal(0);
  readonly cargando = signal(false);
  readonly error = signal('');
  readonly busqueda = signal('');
  readonly incluirArchivados = signal(false);

  readonly formularioAbierto = signal(false);
  readonly registroEnEdicion = signal<Tramite | null>(null);
  readonly guardando = signal(false);
  readonly errorFormulario = signal('');

  readonly credencialAbierta = signal<number | null>(null);
  readonly registroAArchivar = signal<Tramite | null>(null);

  readonly tamanoPagina = TAMANO_PAGINA;
  readonly formatear = formatearValor;

  // Las plantillas de Angular no tienen acceso a `Math`, asi que el calculo se
  // expone como signal derivada en vez de hacerse en el HTML.
  readonly totalPaginas = computed(() => Math.max(1, Math.ceil(this.total() / TAMANO_PAGINA)));
  readonly hayPaginaSiguiente = computed(() => (this.pagina() + 1) * TAMANO_PAGINA < this.total());

  constructor() {
    // El texto se consulta con retardo: sin esto, cada tecla lanzaria una
    // peticion al backend.
    this.terminoBuscado
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntil(this.destruido))
      .subscribe((termino) => {
        this.busqueda.set(termino);
        this.pagina.set(0);
        this.cargar();
      });
  }

  /**
   * Reacciona al cambio de recurso.
   *
   * Se usa `ngOnChanges` y no un `effect`: Angular prohibe escribir signals
   * dentro de un efecto, y reiniciar la vista es precisamente eso. Al navegar
   * entre pestanas el componente se reutiliza, asi que conservar la pagina o
   * el termino de busqueda de la pestana anterior mostraria resultados que no
   * corresponden al recurso que se acaba de abrir.
   */
  ngOnChanges(): void {
    this.pagina.set(0);
    this.busqueda.set('');
    this.incluirArchivados.set(false);
    this.cargar();
  }

  ngOnDestroy(): void {
    this.destruido.next();
    this.destruido.complete();
  }

  cargar(): void {
    this.cargando.set(true);
    this.error.set('');

    this.api
      .listar(this.recurso().endpoint, {
        skip: this.pagina() * TAMANO_PAGINA,
        limit: TAMANO_PAGINA,
        buscar: this.busqueda() || undefined,
        incluirEliminados: this.incluirArchivados(),
      })
      .subscribe({
        next: (respuesta) => {
          this.registros.set(respuesta.items);
          this.total.set(respuesta.total);
          this.cargando.set(false);
        },
        error: () => {
          this.cargando.set(false);
          this.error.set('No se pudo cargar la información.');
        },
      });
  }

  /**
   * Recibe el evento crudo en vez de `$any($event.target).value`.
   *
   * `$any` en la plantilla apaga la comprobacion de tipos justo donde entra
   * dato del exterior, que es donde mas falta hace.
   */
  buscar(evento: Event): void {
    const destino = evento.target as HTMLInputElement | null;
    this.terminoBuscado.next(destino?.value ?? '');
  }

  alternarArchivados(): void {
    this.incluirArchivados.update((valor) => !valor);
    this.pagina.set(0);
    this.cargar();
  }

  paginaAnterior(): void {
    if (this.pagina() > 0) {
      this.pagina.update((n) => n - 1);
      this.cargar();
    }
  }

  paginaSiguiente(): void {
    if ((this.pagina() + 1) * TAMANO_PAGINA < this.total()) {
      this.pagina.update((n) => n + 1);
      this.cargar();
    }
  }

  valorDe(registro: Tramite, campo: string): unknown {
    return (registro as unknown as Record<string, unknown>)[campo];
  }

  estaArchivado(registro: Tramite): boolean {
    return registro.eliminado_en !== null;
  }

  /**
   * Indica si una columna lleva un valor que alguien transcribe a otro portal.
   *
   * Esas celdas se componen en la mono legible, donde una l no se confunde con
   * una I ni un 0 con una O. El nombre y los campos de texto libre no: son
   * lenguaje, y se leen mejor en la proporcional.
   */
  esDato(campo: string): boolean {
    return CAMPOS_DE_DATO.has(campo);
  }

  abrirAlta(): void {
    this.registroEnEdicion.set(null);
    this.errorFormulario.set('');
    this.formularioAbierto.set(true);
  }

  abrirEdicion(registro: Tramite): void {
    this.registroEnEdicion.set(registro);
    this.errorFormulario.set('');
    this.formularioAbierto.set(true);
  }

  cerrarFormulario(): void {
    this.formularioAbierto.set(false);
    this.registroEnEdicion.set(null);
  }

  guardar(cuerpo: CuerpoTramite): void {
    this.guardando.set(true);
    this.errorFormulario.set('');

    const enEdicion = this.registroEnEdicion();
    const peticion = enEdicion
      ? this.api.actualizar(this.recurso().endpoint, enEdicion.id, cuerpo)
      : this.api.crear(this.recurso().endpoint, cuerpo);

    peticion.subscribe({
      next: () => {
        this.guardando.set(false);
        this.cerrarFormulario();
        this.cargar();
      },
      error: (fallo: unknown) => {
        this.guardando.set(false);
        this.errorFormulario.set(this.describirError(fallo));
      },
    });
  }

  confirmarArchivado(registro: Tramite): void {
    this.registroAArchivar.set(registro);
  }

  archivar(): void {
    const registro = this.registroAArchivar();
    if (!registro) {
      return;
    }
    this.api.archivar(this.recurso().endpoint, registro.id).subscribe({
      next: () => {
        this.registroAArchivar.set(null);
        this.cargar();
      },
      error: () => {
        this.registroAArchivar.set(null);
        this.error.set('No se pudo dar de baja el registro.');
      },
    });
  }

  restaurar(registro: Tramite): void {
    this.api.restaurar(this.recurso().endpoint, registro.id).subscribe({
      next: () => this.cargar(),
      error: () => this.error.set('No se pudo reactivar el registro.'),
    });
  }

  private describirError(fallo: unknown): string {
    if (fallo instanceof HttpErrorResponse) {
      if (fallo.status === 422) {
        return 'Revisa los datos: algún campo no tiene el formato esperado.';
      }
      if (fallo.status === 403) {
        return 'Tu rol no permite esta operación.';
      }
    }
    return 'No se pudo guardar el registro.';
  }
}
