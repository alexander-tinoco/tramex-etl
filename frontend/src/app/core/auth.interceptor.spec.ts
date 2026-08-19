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

  it('marks requests to send the session cookie', () => {
    http.get('/api/v1/clientes/').subscribe();

    const peticion = controlador.expectOne('/api/v1/clientes/');
    expect(peticion.request.withCredentials).toBeTrue();
    peticion.flush({});
  });

  it('does not attach any Authorization header', () => {
    // The session travels in a cookie; a token in a header would imply the
    // frontend has it stored somewhere scripts can reach.
    http.get('/api/v1/clientes/').subscribe();

    const peticion = controlador.expectOne('/api/v1/clientes/');
    expect(peticion.request.headers.has('Authorization')).toBeFalse();
    peticion.flush({});
  });

  it('on a 401 it clears the session and redirects to login', () => {
    http.get('/api/v1/clientes/').subscribe({ error: () => undefined });

    controlador
      .expectOne('/api/v1/clientes/')
      .flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(auth.estaAutenticado()).toBeFalse();
    expect(router.navigate).toHaveBeenCalledWith(['/login'], {
      queryParams: { expirada: 'true' },
    });
  });

  it('a 401 on /auth/me does not redirect', () => {
    // On startup with no session, that 401 is the normal response;
    // redirecting would be annoying, and we're already where we need to be.
    http.get('/api/v1/auth/me').subscribe({ error: () => undefined });

    controlador.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(router.navigate).not.toHaveBeenCalled();
  });

  it('does not interfere with other error codes', () => {
    http.get('/api/v1/clientes/').subscribe({ error: () => undefined });

    controlador.expectOne('/api/v1/clientes/').flush(null, { status: 500, statusText: 'Error' });

    expect(router.navigate).not.toHaveBeenCalled();
  });
});
