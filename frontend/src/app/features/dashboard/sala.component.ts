import { Component, OnDestroy, inject, output, signal } from '@angular/core';
import { Subject, debounceTime, distinctUntilChanged, forkJoin, of, switchMap, takeUntil } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { Cliente, Tramite } from '../../models/api.model';
import { CLAVES_RECURSO, ClaveRecurso, RECURSOS } from '../../models/recursos.model';
import { formatearFechaHora } from '../../shared/formato';
import { PictogramaComponent } from '../../shared/pictograma.component';

/** Una fila del tablero: un trámite tocado recientemente, con su carril. */
interface Movimiento {
  recurso: ClaveRecurso;
  registro: Tramite;
}

/**
 * La sala: la pantalla con la que empieza la jornada.
 *
 * No muestra cuatro tarjetas de métrica. La primera acción real de una
 * operadora es encontrar a una persona, así que el buscador ocupa el ancho a
 * escala de rótulo; debajo, lo último que se ha tocado, que responde «qué ha
 * pasado hoy». Los recuentos existen pero como un renglón de marcaje, no como
 * el asunto de la pantalla.
 *
 * La búsqueda va contra `clientes` y no contra cada tabla de trámite: la
 * pregunta es quién es la persona y qué tiene abierto, que es exactamente lo
 * que el modelo relacional hizo posible y la hoja de cálculo no.
 */
@Component({
  selector: 'app-sala',
  standalone: true,
  imports: [PictogramaComponent],
  templateUrl: './sala.component.html',
})
export class SalaComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly destruido = new Subject<void>();
  private readonly termino = new Subject<string>();

  /** Pide al contenedor que abra un carril concreto. */
  readonly abrirRecurso = output<ClaveRecurso>();

  readonly recursos = CLAVES_RECURSO.map((clave) => RECURSOS[clave]);
  readonly conteos = signal<Record<string, number | null>>({});
  readonly movimientos = signal<Movimiento[]>([]);
  readonly cargandoTablero = signal(true);

  readonly busqueda = signal('');
  readonly buscando = signal(false);
  readonly encontrados = signal<Cliente[] | null>(null);

  readonly formatearFechaHora = formatearFechaHora;
  readonly RECURSOS = RECURSOS;

  constructor() {
    this.cargarTablero();

    this.termino
      .pipe(
        debounceTime(280),
        distinctUntilChanged(),
        takeUntil(this.destruido),
        switchMap((texto) => {
          this.busqueda.set(texto);
          if (texto.trim().length < 2) {
            this.buscando.set(false);
            this.encontrados.set(null);
            return of(null);
          }
          this.buscando.set(true);
          return this.api.buscarClientes(texto.trim()).pipe(catchError(() => of(null)));
        }),
      )
      .subscribe((respuesta) => {
        this.buscando.set(false);
        if (respuesta) {
          this.encontrados.set(respuesta.items);
        }
      });
  }

  ngOnDestroy(): void {
    this.destruido.next();
    this.destruido.complete();
  }

  buscar(evento: Event): void {
    const destino = evento.target as HTMLInputElement | null;
    this.termino.next(destino?.value ?? '');
  }

  limpiar(): void {
    this.termino.next('');
    this.busqueda.set('');
    this.encontrados.set(null);
  }

  /**
   * Arma el tablero pidiendo a cada carril sus últimos movimientos.
   *
   * Se piden en paralelo y se entrelazan por fecha. Que falle uno no deja la
   * pantalla en blanco: ese carril simplemente no aporta filas.
   */
  private cargarTablero(): void {
    const peticiones = CLAVES_RECURSO.map((clave) =>
      this.api.listar(RECURSOS[clave].endpoint, { limit: 6, orden: 'reciente' }).pipe(
        map((pagina) => ({
          clave,
          total: pagina.total,
          filas: pagina.items.map((registro) => ({ recurso: clave, registro })),
        })),
        catchError(() => of({ clave, total: null, filas: [] as Movimiento[] })),
      ),
    );

    forkJoin(peticiones).subscribe((resultados) => {
      const conteos: Record<string, number | null> = {};
      const todos: Movimiento[] = [];
      for (const r of resultados) {
        conteos[r.clave] = r.total;
        todos.push(...r.filas);
      }
      this.conteos.set(conteos);
      this.movimientos.set(
        todos
          .sort(
            (a, b) =>
              new Date(b.registro.actualizado_en).getTime() -
              new Date(a.registro.actualizado_en).getTime(),
          )
          .slice(0, 12),
      );
      this.cargandoTablero.set(false);
    });
  }

  conteoDe(clave: string): string {
    const valor = this.conteos()[clave];
    return valor === null || valor === undefined ? '—' : String(valor);
  }

  totalPersonas(): string {
    const valores = Object.values(this.conteos());
    if (!valores.length || valores.some((v) => v === null)) {
      return '—';
    }
    return String(valores.reduce((suma: number, v) => suma + (v ?? 0), 0));
  }

  nombreCompleto(cliente: Cliente): string {
    return [cliente.nombre, cliente.apellido].filter(Boolean).join(' ');
  }

  /**
   * Lee el pasaporte de un trámite cualquiera.
   *
   * Tres de los cuatro tipos lo tienen y Pasaportes no, así que el acceso se
   * acota aquí en TypeScript en lugar de escapar la comprobación de tipos con
   * `$any` en la plantilla, que es donde menos conviene apagarla.
   */
  pasaporteDe(registro: Tramite): string {
    return 'numero_pasaporte' in registro ? (registro.numero_pasaporte ?? '—') : '—';
  }
}
