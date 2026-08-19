import { Component, OnDestroy, inject, output, signal } from '@angular/core';
import { Subject, debounceTime, distinctUntilChanged, forkJoin, of, switchMap, takeUntil } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { Cliente, Tramite } from '../../models/api.model';
import { CLAVES_RECURSO, ClaveRecurso, RECURSOS } from '../../models/recursos.model';
import { formatearFechaHora } from '../../shared/formato';
import { PictogramaComponent } from '../../shared/pictograma.component';

/** One row of the board: a tramite touched recently, with its lane. */
interface Movimiento {
  recurso: ClaveRecurso;
  registro: Tramite;
}

/**
 * The floor: the screen the workday starts on.
 *
 * It doesn't show four metric cards. An operator's first real action is
 * finding a person, so the search bar spans the width at signage scale;
 * below it, whatever was touched last, which answers "what happened today".
 * The counts still exist, but as a tally row, not as the point of the screen.
 *
 * Search targets `clientes`, not each tramite table: the question is who this
 * person is and what they have open, which is exactly what the relational
 * model made possible and the spreadsheet couldn't.
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

  /** Asks the container to open a specific lane. */
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
   * Builds the board by asking each lane for its latest activity.
   *
   * The requests go out in parallel and get interleaved by date. If one
   * fails, the screen doesn't go blank: that lane simply contributes no rows.
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
   * Reads the passport of any tramite.
   *
   * Three of the four types have it and Pasaportes doesn't, so the access is
   * scoped here in TypeScript instead of escaping the type checker with
   * `$any` in the template, which is the last place it should be turned off.
   */
  pasaporteDe(registro: Tramite): string {
    return 'numero_pasaporte' in registro ? (registro.numero_pasaporte ?? '—') : '—';
  }
}
