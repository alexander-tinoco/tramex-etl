import { Routes } from '@angular/router';
import { adminGuard, authGuard } from './core/guards';

/**
 * Rutas de la aplicacion.
 *
 * Las vistas se cargan de forma diferida: el dashboard arrastra la tabla, los
 * formularios y el panel de auditoria, y no tiene sentido descargar todo eso
 * para mostrar una pantalla de login.
 */
export const routes: Routes = [
  {
    path: 'login',
    title: 'Iniciar sesión · Tramex',
    loadComponent: () => import('./features/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'dashboard',
    title: 'Panel · Tramex',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
  },
  {
    path: 'auditoria',
    title: 'Auditoría · Tramex',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/auditoria/panel-auditoria.component').then((m) => m.PanelAuditoriaComponent),
  },
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: '/dashboard' },
];
