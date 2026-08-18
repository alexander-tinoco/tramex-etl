import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AuthService } from './auth.service';
import { Usuario } from '../models/api.model';

const USUARIO: Usuario = {
  id: 1,
  correo_electronico: 'operadora@example.com',
  nombre: 'Operadora',
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

  it('arranca sin sesión y sin haberla resuelto', () => {
    expect(servicio.estaAutenticado()).toBeFalse();
    expect(servicio.sesionResuelta()).toBeFalse();
    expect(servicio.usuario()).toBeNull();
  });

  it('envía las credenciales como formulario y con credenciales', () => {
    servicio.iniciarSesion('operadora@example.com', 'clave-larga-1234').subscribe();

    const peticion = http.expectOne('/api/v1/auth/token');
    expect(peticion.request.method).toBe('POST');
    expect(peticion.request.withCredentials).toBeTrue();
    expect(peticion.request.headers.get('Content-Type')).toBe('application/x-www-form-urlencoded');
    expect(peticion.request.body).toContain('username=operadora%40example.com');

    peticion.flush({
      access_token: 'jwt-de-prueba',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: USUARIO,
    });

    expect(servicio.estaAutenticado()).toBeTrue();
    expect(servicio.usuario()?.correo_electronico).toBe('operadora@example.com');
  });

  it('no guarda el token en localStorage', () => {
    // Es el punto del cambio: la sesion vive en una cookie httpOnly, invisible
    // para JavaScript. Guardarla aqui reintroduciria la exposicion a XSS.
    servicio.iniciarSesion('operadora@example.com', 'clave-larga-1234').subscribe();
    http.expectOne('/api/v1/auth/token').flush({
      access_token: 'jwt-de-prueba',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: USUARIO,
    });

    expect(Object.keys(localStorage)).toEqual([]);
    expect(JSON.stringify(localStorage)).not.toContain('jwt-de-prueba');
  });

  it('marca el rol de administrador', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush({ ...USUARIO, rol: 'admin' });

    expect(servicio.esAdmin()).toBeTrue();
  });

  it('un operador no es administrador', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush(USUARIO);

    expect(servicio.esAdmin()).toBeFalse();
  });

  it('un 401 al cargar la sesión deja el estado limpio y resuelto', () => {
    servicio.cargarSesion().subscribe({ error: () => undefined });
    http.expectOne('/api/v1/auth/me').flush(null, { status: 401, statusText: 'Unauthorized' });

    expect(servicio.estaAutenticado()).toBeFalse();
    // Resuelto, aunque sin sesion: la aplicacion ya sabe que mostrar.
    expect(servicio.sesionResuelta()).toBeTrue();
  });

  it('cerrar sesión descarta el usuario', () => {
    servicio.cargarSesion().subscribe();
    http.expectOne('/api/v1/auth/me').flush(USUARIO);

    servicio.cerrarSesion().subscribe();
    http.expectOne('/api/v1/auth/logout').flush(null);

    expect(servicio.usuario()).toBeNull();
    expect(servicio.estaAutenticado()).toBeFalse();
  });
});
