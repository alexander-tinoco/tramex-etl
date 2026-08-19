import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter,
} from '@angular/router';
import { Observable, isObservable } from 'rxjs';
import { adminGuard, authGuard } from './guards';
import { Usuario } from '../models/api.model';
import { AuthService } from './auth.service';

const RUTA = {} as ActivatedRouteSnapshot;
const ESTADO = {} as RouterStateSnapshot;

describe('guards', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => TestBed.resetTestingModule());

  describe('authGuard', () => {
    it('lets the request through once the session is already resolved', () => {
      auth.cargarSesion().subscribe();
      http.expectOne('/api/v1/auth/me').flush({
        id: 1,
        correo_electronico: 'operator@example.com',
        nombre: 'Operator',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });

      const resultado = TestBed.runInInjectionContext(() => authGuard(RUTA, ESTADO));
      expect(resultado).toBeTrue();
    });

    it('asks the API when the state is not yet known', (done) => {
      // The cookie is httpOnly: the guard can't inspect it, and only the API
      // can confirm whether there's a session.
      const resultado = TestBed.runInInjectionContext(() => authGuard(RUTA, ESTADO));
      expect(isObservable(resultado)).toBeTrue();

      (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
        expect(valor).toBeTrue();
        done();
      });

      http.expectOne('/api/v1/auth/me').flush({
        id: 1,
        correo_electronico: 'operator@example.com',
        nombre: 'Operator',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });
    });

    it('redirects to login when there is no session', (done) => {
      const resultado = TestBed.runInInjectionContext(() => authGuard(RUTA, ESTADO));

      (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
        expect(valor instanceof UrlTree).toBeTrue();
        expect((valor as UrlTree).toString()).toBe('/login');
        done();
      });

      http.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
    });
  });

  describe('adminGuard', () => {
    function autenticarComo(rol: 'admin' | 'operador'): void {
      auth.cargarSesion().subscribe();
      http.expectOne('/api/v1/auth/me').flush({
        id: 1,
        correo_electronico: 'person@example.com',
        nombre: 'Person',
        rol,
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });
    }

    it('lets an administrator through', () => {
      autenticarComo('admin');
      expect(TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO))).toBeTrue();
    });

    it('sends an operator back to the panel', () => {
      // It's only a convenience for the interface: the API checks the role
      // again on every request, which is where the data is actually protected.
      autenticarComo('operador');
      const resultado = TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO));
      expect(resultado instanceof UrlTree).toBeTrue();
      expect((resultado as UrlTree).toString()).toBe('/dashboard');
    });
  });

  it('the router is available in the test context', () => {
    expect(TestBed.inject(Router)).toBeTruthy();
  });
});

describe('adminGuard with an unresolved session', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => TestBed.resetTestingModule());

  function usuario(rol: 'admin' | 'operador'): Usuario {
    return {
      id: 1,
      correo_electronico: 'person@example.com',
      nombre: 'Person',
      rol,
      activo: true,
      ultimo_acceso_en: null,
      cargado_en: '2026-08-17T10:00:00',
    };
  }

  it('resolves the session before deciding, when entering via a direct link', (done) => {
    // Angular evaluates a route's guards in parallel, not in a chain: if this
    // one didn't query on its own, it would see "no session" and bounce a
    // legitimate administrator back to the panel every time the page reloads.
    const resultado = TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO));
    expect(isObservable(resultado)).toBeTrue();

    (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
      expect(valor).toBeTrue();
      done();
    });

    http.expectOne('/api/v1/auth/me').flush(usuario('admin'));
  });

  it('sends the user back to the panel if they turn out to be an operator', (done) => {
    const resultado = TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO));

    (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
      expect(valor instanceof UrlTree).toBeTrue();
      expect((valor as UrlTree).toString()).toBe('/dashboard');
      done();
    });

    http.expectOne('/api/v1/auth/me').flush(usuario('operador'));
  });

  it('sends to login when there is no session', (done) => {
    const resultado = TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO));

    (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
      expect((valor as UrlTree).toString()).toBe('/login');
      done();
    });

    http.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });
  });
});
