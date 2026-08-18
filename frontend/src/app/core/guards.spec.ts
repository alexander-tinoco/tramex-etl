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
    it('deja pasar cuando ya hay sesión resuelta', () => {
      auth.cargarSesion().subscribe();
      http.expectOne('/api/v1/auth/me').flush({
        id: 1,
        correo_electronico: 'operadora@example.com',
        nombre: 'Operadora',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });

      const resultado = TestBed.runInInjectionContext(() => authGuard(RUTA, ESTADO));
      expect(resultado).toBeTrue();
    });

    it('consulta a la API cuando el estado aún no se conoce', (done) => {
      // La cookie es httpOnly: el guard no puede inspeccionarla y solo la API
      // puede confirmar si hay sesion.
      const resultado = TestBed.runInInjectionContext(() => authGuard(RUTA, ESTADO));
      expect(isObservable(resultado)).toBeTrue();

      (resultado as Observable<boolean | UrlTree>).subscribe((valor) => {
        expect(valor).toBeTrue();
        done();
      });

      http.expectOne('/api/v1/auth/me').flush({
        id: 1,
        correo_electronico: 'operadora@example.com',
        nombre: 'Operadora',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });
    });

    it('redirige al login si no hay sesión', (done) => {
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
        correo_electronico: 'persona@example.com',
        nombre: 'Persona',
        rol,
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      });
    }

    it('deja pasar a un administrador', () => {
      autenticarComo('admin');
      expect(TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO))).toBeTrue();
    });

    it('devuelve a un operador al panel', () => {
      // Es solo una comodidad de la interfaz: la API vuelve a comprobar el rol
      // en cada peticion, que es donde realmente se protegen los datos.
      autenticarComo('operador');
      const resultado = TestBed.runInInjectionContext(() => adminGuard(RUTA, ESTADO));
      expect(resultado instanceof UrlTree).toBeTrue();
      expect((resultado as UrlTree).toString()).toBe('/dashboard');
    });
  });

  it('el router está disponible en el contexto de prueba', () => {
    expect(TestBed.inject(Router)).toBeTruthy();
  });
});
