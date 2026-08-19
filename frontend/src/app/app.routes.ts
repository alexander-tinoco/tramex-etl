import { Routes } from '@angular/router';
import { adminGuard, authGuard } from './core/guards';

/**
 * Application routes.
 *
 * Views are lazy-loaded: the dashboard pulls in the table, the forms and the
 * audit panel, and there's no point downloading all of that to show a login
 * screen.
 */
export const routes: Routes = [
  {
    path: 'login',
    title: 'Sign in · Tramex',
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
    title: 'Audit Log · Tramex',
    canActivate: [authGuard, adminGuard],
    loadComponent: () =>
      import('./features/auditoria/panel-auditoria.component').then((m) => m.PanelAuditoriaComponent),
  },
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: '/dashboard' },
];
