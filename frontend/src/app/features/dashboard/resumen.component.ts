import { Component, inject, signal } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { ApiService } from '../../core/api.service';
import { CLAVES_RECURSO, ClaveRecurso, RECURSOS } from '../../models/recursos.model';

/**
 * Panel de resumen: cuantos tramites vigentes hay de cada tipo.
 *
 * Los conteos se piden en paralelo con `limit=1`: lo unico que interesa es el
 * campo `total` de la respuesta paginada, no las filas.
 */
@Component({
  selector: 'app-resumen',
  standalone: true,
  templateUrl: './resumen.component.html',
})
export class ResumenComponent {
  private readonly api = inject(ApiService);

  readonly recursos = CLAVES_RECURSO.map((clave) => RECURSOS[clave]);
  readonly conteos = signal<Record<string, number | null>>({});
  readonly cargando = signal(true);

  constructor() {
    this.cargar();
  }

  private cargar(): void {
    const peticiones = Object.fromEntries(
      CLAVES_RECURSO.map((clave) => [
        clave,
        this.api.listar(RECURSOS[clave].endpoint, { limit: 1 }).pipe(
          map((respuesta) => respuesta.total),
          // Que falle el conteo de un recurso no debe dejar el panel entero en
          // blanco: se muestra un guion en esa tarjeta y las demas siguen.
          catchError(() => of(null)),
        ),
      ]),
    );

    forkJoin(peticiones).subscribe((resultado) => {
      this.conteos.set(resultado as Record<ClaveRecurso, number | null>);
      this.cargando.set(false);
    });
  }

  conteoDe(clave: string): string {
    const valor = this.conteos()[clave];
    return valor === null || valor === undefined ? '—' : String(valor);
  }
}
