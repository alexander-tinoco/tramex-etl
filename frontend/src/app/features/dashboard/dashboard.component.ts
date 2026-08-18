import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { CLAVES_RECURSO, ClaveRecurso, RECURSOS } from '../../models/recursos.model';
import { ResumenComponent } from './resumen.component';
import { TablaTramitesComponent } from '../tramites/tabla-tramites.component';

type Seccion = 'resumen' | ClaveRecurso;

/**
 * Contenedor del panel.
 *
 * Su unica responsabilidad es la navegacion y el marco: que seccion esta
 * activa, quien ha iniciado sesion y si la base responde. El contenido lo
 * aportan componentes propios. La version anterior de este archivo tenia 378
 * lineas y mezclaba navegacion, resumen, tabla, formulario, tres modales,
 * paginacion y busqueda.
 */
@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, ResumenComponent, TablaTramitesComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly secciones = CLAVES_RECURSO.map((clave) => RECURSOS[clave]);
  readonly seccion = signal<Seccion>('resumen');
  readonly baseConectada = signal<boolean | null>(null);

  readonly usuario = this.auth.usuario;
  readonly esAdmin = this.auth.esAdmin;

  readonly recursoActivo = computed(() => {
    const actual = this.seccion();
    return actual === 'resumen' ? null : RECURSOS[actual];
  });

  readonly titulo = computed(() => this.recursoActivo()?.titulo ?? 'Resumen del sistema');

  constructor() {
    this.api.estadoSalud().subscribe({
      next: (estado) => this.baseConectada.set(estado.database === 'connected'),
      // La sonda tambien falla si la API entera esta caida; en ambos casos lo
      // util para quien opera es lo mismo: los datos no estan disponibles.
      error: () => this.baseConectada.set(false),
    });
  }

  irA(seccion: Seccion): void {
    this.seccion.set(seccion);
  }

  cerrarSesion(): void {
    this.auth.cerrarSesion().subscribe({
      next: () => void this.router.navigate(['/login']),
      // Aunque la peticion falle, la sesion local se descarta: dejar al
      // usuario dentro tras pulsar "cerrar sesion" seria lo peor de ambos
      // mundos.
      error: () => {
        this.auth.limpiar();
        void this.router.navigate(['/login']);
      },
    });
  }
}
