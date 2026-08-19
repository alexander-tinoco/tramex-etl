import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AsientoAuditoria } from '../../models/api.model';
import { formatearFechaHora, formatearTexto } from '../../shared/formato';
import { PictogramaComponent } from '../../shared/pictograma.component';

/**
 * Actions worth filtering the audit log by.
 *
 * `valor` mirrors the backend's `Accion` string literals verbatim (used as
 * the `accion` query parameter); only `etiqueta`, the display label, is
 * translated.
 */
const ACCIONES = [
  { valor: '', etiqueta: 'All actions' },
  { valor: 'credencial_consultada', etiqueta: 'Credentials viewed' },
  { valor: 'credencial_ilegible', etiqueta: 'Unreadable credentials' },
  { valor: 'login_exitoso', etiqueta: 'Successful logins' },
  { valor: 'login_fallido', etiqueta: 'Failed logins' },
  { valor: 'login_bloqueado', etiqueta: 'Blocked accounts' },
  { valor: 'registro_creado', etiqueta: 'Records created' },
  { valor: 'registro_actualizado', etiqueta: 'Records updated' },
  { valor: 'registro_archivado', etiqueta: 'Records archived' },
  { valor: 'registro_purgado', etiqueta: 'Records purged' },
];

const TAMANO_PAGINA = 25;

/**
 * Audit log (admins only).
 *
 * This is the screen that makes the system's promise verifiable: that every
 * access to a client credential is recorded and can be reviewed later.
 */
@Component({
  selector: 'app-panel-auditoria',
  standalone: true,
  imports: [RouterLink, PictogramaComponent],
  templateUrl: './panel-auditoria.component.html',
})
export class PanelAuditoriaComponent {
  private readonly api = inject(ApiService);

  readonly acciones = ACCIONES;
  readonly asientos = signal<AsientoAuditoria[]>([]);
  readonly total = signal(0);
  readonly pagina = signal(0);
  readonly filtro = signal('');
  readonly cargando = signal(true);
  readonly error = signal('');

  readonly tamanoPagina = TAMANO_PAGINA;
  readonly totalPaginas = computed(() => Math.max(1, Math.ceil(this.total() / TAMANO_PAGINA)));
  readonly hayPaginaSiguiente = computed(() => (this.pagina() + 1) * TAMANO_PAGINA < this.total());

  readonly formatearFechaHora = formatearFechaHora;
  readonly formatearTexto = formatearTexto;

  constructor() {
    this.cargar();
  }

  cargar(): void {
    this.cargando.set(true);
    this.error.set('');

    this.api
      .listarAuditoria(this.pagina() * TAMANO_PAGINA, TAMANO_PAGINA, this.filtro() || undefined)
      .subscribe({
        next: (respuesta) => {
          this.asientos.set(respuesta.items);
          this.total.set(respuesta.total);
          this.cargando.set(false);
        },
        error: () => {
          this.cargando.set(false);
          this.error.set('Could not load the audit log.');
        },
      });
  }

  cambiarFiltro(evento: Event): void {
    const destino = evento.target as HTMLSelectElement | null;
    this.filtro.set(destino?.value ?? '');
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
    if (this.hayPaginaSiguiente()) {
      this.pagina.update((n) => n + 1);
      this.cargar();
    }
  }

  claseNivel(nivel: string): string {
    switch (nivel) {
      case 'ALERTA':
        return 'alerta';
      case 'ADVERTENCIA':
        return 'advertencia';
      default:
        return 'info';
    }
  }

  /** Display label for a level; falls back to the raw value for anything unmapped. */
  etiquetaNivel(nivel: string): string {
    switch (nivel) {
      case 'ALERTA':
        return 'Alert';
      case 'ADVERTENCIA':
        return 'Warning';
      case 'INFO':
        return 'Info';
      default:
        return nivel;
    }
  }

  /** Display label for an action code, reusing the same map as the filter. */
  etiquetaAccion(valor: string): string {
    return ACCIONES.find((accion) => accion.valor === valor)?.etiqueta ?? valor;
  }
}
