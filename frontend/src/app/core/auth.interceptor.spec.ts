import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let controlador: HttpTestingController;
  let router: jasmine.SpyObj<Router>;
  let auth: AuthService;

  beforeEach(() => {
    router = jasmine.createSpyObj<Router>('Router', ['navigate'], { url: '/dashboard' });
    router.navigate.and.resolveTo(true);

    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        { provide: Router, useValue: router },
      ],
    });

    http = TestBed.inject(HttpClient);
    controlador = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => controlador.verify());

  it('marca las peticiones para que envíen la cookie de sesión', () => {
    http.get('/api/v1/clientes/').subscribe();

    const peticion = controlador.expectOne('/api/v1/clientes/');
    expect(peticion.request.withCredentials).toBeTrue();
    peticion.flush({});
  });

  it('no adjunta ninguna cabecera Authorization', () => {
    // La sesion va en cookie; un token en cabecera implicaria que el frontend
    // lo tiene guardado en algun sitio accesible por scripts.
    http.get('/api/v1/clientes/').subscribe();

    const peticion = controlador.expectOne('/api/v1/clientes/');
    expect(peticion.request.headers.has('Authorization')).toBeFalse();
    peticion.flush({});
  });

  it('ante un 401 limpia la sesión y manda al login', () => {
    http.get('/api/v1/clientes/').subscribe({ error: () => undefined });

    controlador
      .expectOne('/api/v1/clientes/')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(auth.estaAutenticado()).toBeFalse();
    expect(router.navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { expirada: 'true' },
    });
  });

  it('un 401 en /auth/me no redirige', () => {
    // Al arrancar sin sesion, ese 401 es la respuesta normal; redirigir seria
    // molesto y ademas ya estamos donde toca.
    http.get('/api/v1/auth/me').subscribe({ error: () => undefined });

    controlador.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('no interfiere con otros códigos de error', () => {
    http.get('/api/v1/clientes/').subscribe({ error: () => undefined });

    controlador.expectOne('/api/v1/clientes/').flush(null, { status: 500, statusText: 'Error' });

    expect(router.navigate).not.toHaveBeenCalled();
  });
});
