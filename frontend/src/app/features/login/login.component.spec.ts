import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ActivatedRoute, Router, convertToParamMap } from '@angular/router';
import { LoginComponent } from './login.component';

function crearComponente(parametros: Record<string, string> = {}): {
  fixture: ComponentFixture<LoginComponent>;
  http: HttpTestingController;
  router: jasmine.SpyObj<Router>;
} {
  const router = jasmine.createSpyObj<Router>('Router', ['navigate']);
  router.navigate.and.resolveTo(true);

  TestBed.configureTestingModule({
    imports: [LoginComponent],
    providers: [
      provideHttpClient(),
      provideHttpClientTesting(),
      { provide: Router, useValue: router },
      {
        provide: ActivatedRoute,
        useValue: { snapshot: { queryParamMap: convertToParamMap(parametros) } },
      },
    ],
  });

  return {
    fixture: TestBed.createComponent(LoginComponent),
    http: TestBed.inject(HttpTestingController),
    router,
  };
}

describe('LoginComponent', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('se crea correctamente', () => {
    const { fixture } = crearComponente();
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('la contraseña arranca oculta y se puede revelar', () => {
    const { fixture } = crearComponente();
    const componente = fixture.componentInstance;

    expect(componente.mostrarContrasena()).toBeFalse();
    componente.alternarVisibilidad();
    expect(componente.mostrarContrasena()).toBeTrue();
  });

  it('no envía nada si faltan credenciales', () => {
    const { fixture, http } = crearComponente();
    fixture.componentInstance.enviar(new Event('submit'));
    http.expectNone('/api/v1/auth/token');
  });

  it('navega al panel tras un inicio de sesión correcto', () => {
    const { fixture, http, router } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operadora@example.com';
    componente.contrasena = 'clave-larga-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').flush({
      access_token: 'jwt',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: {
        id: 1,
        correo_electronico: 'operadora@example.com',
        nombre: 'Operadora',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      },
    });

    expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);
    expect(componente.cargando()).toBeFalse();
  });

  it('muestra un mensaje claro ante credenciales incorrectas', () => {
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operadora@example.com';
    componente.contrasena = 'equivocada';
    componente.enviar(new Event('submit'));

    http
      .expectOne('/api/v1/auth/token')
      .flush({ detail: 'Credenciales incorrectas.' }, { status: 401, statusText: 'Unauthorized' });

    expect(componente.error()).toContain('incorrectos');
  });

  it('distingue una cuenta bloqueada de unas credenciales incorrectas', () => {
    // Decir "credenciales incorrectas" cuando la cuenta esta bloqueada haria
    // que la persona siguiera probando contrasenas sin entender que pasa.
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operadora@example.com';
    componente.contrasena = 'clave-larga-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').flush(
      { detail: 'Cuenta bloqueada temporalmente por intentos fallidos. Vuelve a intentar en 14 minuto(s).' },
      { status: 429, statusText: 'Too Many Requests' },
    );

    expect(componente.error()).toContain('bloqueada');
  });

  it('avisa cuando no hay conexión con el servidor', () => {
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operadora@example.com';
    componente.contrasena = 'clave-larga-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').error(new ProgressEvent('error'), { status: 0 });

    expect(componente.error()).toContain('conexión');
  });

  it('avisa cuando la sesión anterior expiró', () => {
    const { fixture } = crearComponente({ expirada: 'true' });
    expect(fixture.componentInstance.sesionExpirada()).toBeTrue();
  });
});
