import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { CLAVES_RECURSO, ClaveRecurso, RECURSOS } from '../../models/recursos.model';
import { SalaComponent } from './sala.component';
import { TablaTramitesComponent } from '../tramites/tabla-tramites.component';
import { PictogramaComponent } from '../../shared/pictograma.component';

type Seccion = 'sala' | ClaveRecurso;

/**
 * Panel shell.
 *
 * Its only responsibility is navigation and the frame: which section is
 * active, who is signed in, and whether the database responds. The content
 * comes from its own components. The previous version of this file was 378
 * lines and mixed navigation, summary, table, form, three modals, pagination
 * and search.
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, SalaComponent, TablaTramitesComponent, PictogramaComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly secciones = CLAVES_RECURSO.map((clave) => RECURSOS[clave]);
  readonly seccion = signal<Seccion>('sala');
  readonly baseConectada = signal<boolean | null>(null);

  readonly usuario = this.auth.usuario;
  readonly esAdmin = this.auth.esAdmin;

  readonly recursoActivo = computed(() => {
    const actual = this.seccion();
    return actual === 'sala' ? null : RECURSOS[actual];
  });

  readonly titulo = computed(() => this.recursoActivo()?.titulo ?? 'Floor');

  /** The header says what the lane is about; it doesn't just repeat its name. */
  readonly subtitulo = computed(
    () =>
      this.recursoActivo()?.descripcion ??
      'Search for a person and open their full record. Below, whatever was touched last.',
  );

  constructor() {
    this.api.estadoSalud().subscribe({
      next: (estado) => this.baseConectada.set(estado.database === 'connected'),
      // The probe also fails if the whole API is down; either way the
      // operator sees the same thing: the data isn't available.
      error: () => this.baseConectada.set(false),
    });
  }

  irA(seccion: Seccion): void {
    this.seccion.set(seccion);
  }

  cerrarSesion(): void {
    this.auth.cerrarSesion().subscribe({
      next: () => void this.router.navigate(['/login']),
      // Even if the request fails, the local session is discarded: leaving
      // the user signed in after pressing "sign out" would be the worst of
      // both worlds.
      error: () => {
        this.auth.limpiar();
        void this.router.navigate(['/login']);
      },
    });
  }
}
