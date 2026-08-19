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

/** Columns whose content someone later types into a consular portal. */
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
 * Table for one tramite resource, with search, pagination and actions.
 *
 * It's the same component for all four resources: the difference comes in
 * through configuration. In the previous version all of this logic lived
 * inside a single 378-line component that also handled navigation, the
 * summary and three modals.
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

  // Angular templates have no access to `Math`, so the calculation is exposed
  // as a derived signal instead of being done in the HTML.
  readonly totalPaginas = computed(() => Math.max(1, Math.ceil(this.total() / TAMANO_PAGINA)));
  readonly hayPaginaSiguiente = computed(() => (this.pagina() + 1) * TAMANO_PAGINA < this.total());

  constructor() {
    // The query is debounced: without this, every keystroke would fire a
    // request to the backend.
    this.terminoBuscado
      .pipe(debounceTime(300), distinctUntilChanged(), takeUntil(this.destruido))
      .subscribe((termino) => {
        this.busqueda.set(termino);
        this.pagina.set(0);
        this.cargar();
      });
  }

  /**
   * Reacts to a change of resource.
   *
   * `ngOnChanges` is used instead of an `effect`: Angular forbids writing to
   * signals inside an effect, and resetting the view is exactly that. The
   * component is reused when navigating between tabs, so keeping the previous
   * tab's page or search term would show results that don't belong to the
   * resource that was just opened.
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
          this.error.set('Could not load the data.');
        },
      });
  }

  /**
   * Receives the raw event instead of `$any($event.target).value`.
   *
   * `$any` in the template turns off type checking right where data enters
   * from the outside world, which is exactly where it's needed most.
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
   * Indicates whether a column carries a value someone will later transcribe
   * into another portal.
   *
   * Those cells are set in the legible mono font, where an l is never
   * confused with an I nor a 0 with an O. The name and free-text fields
   * aren't: they're language, and read better in the proportional face.
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
        this.error.set('Could not archive the record.');
      },
    });
  }

  restaurar(registro: Tramite): void {
    this.api.restaurar(this.recurso().endpoint, registro.id).subscribe({
      next: () => this.cargar(),
      error: () => this.error.set('Could not restore the record.'),
    });
  }

  private describirError(fallo: unknown): string {
    if (fallo instanceof HttpErrorResponse) {
      if (fallo.status === 422) {
        return "Check the data: some field doesn't have the expected format.";
      }
      if (fallo.status === 403) {
        return 'Your role does not allow this operation.';
      }
    }
    return 'Could not save the record.';
  }
}
