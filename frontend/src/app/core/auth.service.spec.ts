import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';
import { Usuario } from '../models/api.model';

const USUARIO: Usuario = {
  id: 1,
  correo_electronico: 'operator@example.com',
  nombre: 'Operator',
  rol: 'operador',
  activo: true,
  ultimo_acceso_en: null,
  cargado_en: '2026-08-17T10:00:00',
};

describe('AuthService', () => {
  let servicio: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    servicio = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('starts with no session and unresolved', () => {
    expect(servicio.estaAutenticado()).toBeFalse();
    expect(servicio.sesionResuelta()).toBeFalse();
    expect(servicio.usuario()).toBeNull();
  });

  it('sends credentials as a form, with credentials included', () => {
    servicio.iniciarSesion('operator@example.com', 'a-long-password-1234').subscribe();

    const peticion = http.expectOne('/api/v1/auth/token');
    expect(peticion.request.method).toBe('POST');
    expect(peticion.request.withCredentials).toBeTrue();
    expect(peticion.request.headers.get('Content-Type')).toBe('application/x-www-form-urlencoded');
    expect(peticion.request.body).toContain('username=operator%40example.com');

    peticion.flush({
      access_token: 'test-jwt',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: USUARIO,
    });

    expect(servicio.estaAutenticado()).toBeTrue();
    expect(servicio.usuario()?.correo_electronico).toBe('operator@example.com');
  });

  it('does not store the token in localStorage', () => {
    // This is the whole point of the change: the session lives in an
    // httpOnly cookie, invisible to JavaScript. Storing it here would
    // reintroduce exposure to XSS.
    servicio.iniciarSesion('operator@example.com', 'a-long-password-1234').subscribe();
    http.expectOne('/api/v1/auth/token').flush({
      access_token: 'test-jwt',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: USUARIO,
    });

    expect(Object.keys(localStorage)).toEqual([]);
    expect(JSON.stringify(localStorage)).not.toContain('test-jwt');
  });

  it('marks the administrator role', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush({ ...USUARIO, rol: 'admin' });

    expect(servicio.esAdmin()).toBeTrue();
  });

  it('an operator is not an administrator', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush(USUARIO);

    expect(servicio.esAdmin()).toBeFalse();
  });

  it('a 401 while loading the session leaves the state clean and resolved', () => {
    servicio.cargarSesion().subscribe({ error: () => undefined });
    http.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(servicio.estaAutenticado()).toBeFalse();
    // Resolved, even without a session: the application already knows what to show.
    expect(servicio.sesionResuelta()).toBeTrue();
  });

  it('signing out discards the user', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush(USUARIO);

    servicio.cerrarSesion().subscribe();
    http.expectOne('/api/v1/auth/logout').flush(null);

    expect(servicio.usuario()).toBeNull();
    expect(servicio.estaAutenticado()).toBeFalse();
  });
});
