import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AsientoAuditoria } from '../../models/api.model';
import { formatearFechaHora, formatearTexto } from '../../shared/formato';
import { PictogramaComponent } from '../../shared/pictograma.component';

/** Acciones por las que tiene sentido filtrar la bitacora. */
const ACCIONES = [
  { valor: '', etiqueta: 'Todas las acciones' },
  { valor: 'credencial_consultada', etiqueta: 'Credenciales consultadas' },
  { valor: 'credencial_ilegible', etiqueta: 'Credenciales ilegibles' },
  { valor: 'login_exitoso', etiqueta: 'Inicios de sesión' },
  { valor: 'login_fallido', etiqueta: 'Inicios fallidos' },
  { valor: 'login_bloqueado', etiqueta: 'Cuentas bloqueadas' },
  { valor: 'registro_creado', etiqueta: 'Altas' },
  { valor: 'registro_actualizado', etiqueta: 'Modificaciones' },
  { valor: 'registro_archivado', etiqueta: 'Bajas' },
  { valor: 'registro_purgado', etiqueta: 'Purgas' },
];

const TAMANO_PAGINA = 25;

/**
 * Bitacora de auditoria (solo administradores).
 *
 * Es la pantalla que hace verificable la promesa del sistema: que cada acceso
 * a una credencial de cliente queda registrado y se puede consultar despues.
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
          this.error.set('No se pudo cargar la bitácora.');
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
}
