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

  it('creates successfully', () => {
    const { fixture } = crearComponente();
    fixture.detectChanges();
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('the password starts hidden and can be revealed', () => {
    const { fixture } = crearComponente();
    const componente = fixture.componentInstance;

    expect(componente.mostrarContrasena()).toBeFalse();
    componente.alternarVisibilidad();
    expect(componente.mostrarContrasena()).toBeTrue();
  });

  it('sends nothing if credentials are missing', () => {
    const { fixture, http } = crearComponente();
    fixture.componentInstance.enviar(new Event('submit'));
    http.expectNone('/api/v1/auth/token');
  });

  it('navigates to the panel after a successful sign-in', () => {
    const { fixture, http, router } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operator@example.com';
    componente.contrasena = 'a-long-password-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').flush({
      access_token: 'jwt',
      token_type: 'bearer',
      expira_en_minutos: 480,
      usuario: {
        id: 1,
        correo_electronico: 'operator@example.com',
        nombre: 'Operator',
        rol: 'operador',
        activo: true,
        ultimo_acceso_en: null,
        cargado_en: '2026-08-17T10:00:00',
      },
    });

    expect(router.navigate).toHaveBeenCalledWith(['/dashboard']);
    expect(componente.cargando()).toBeFalse();
  });

  it('shows a clear message on incorrect credentials', () => {
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operator@example.com';
    componente.contrasena = 'wrong';
    componente.enviar(new Event('submit'));

    http
      .expectOne('/api/v1/auth/token')
      .flush({ detail: 'Incorrect credentials.' }, { status: 401, statusText: 'Unauthorized' });

    expect(componente.error()).toContain('Incorrect');
  });

  it('distinguishes a locked account from incorrect credentials', () => {
    // Saying "incorrect credentials" while the account is locked would leave
    // the person trying passwords without understanding what's going on.
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operator@example.com';
    componente.contrasena = 'a-long-password-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').flush(
      { detail: 'Account temporarily locked due to failed attempts. Try again in 14 minute(s).' },
      { status: 429, statusText: 'Too Many Requests' },
    );

    expect(componente.error()).toContain('locked');
  });

  it('warns when there is no connection to the server', () => {
    const { fixture, http } = crearComponente();
    const componente = fixture.componentInstance;

    componente.correo = 'operator@example.com';
    componente.contrasena = 'a-long-password-1234';
    componente.enviar(new Event('submit'));

    http.expectOne('/api/v1/auth/token').error(new ProgressEvent('error'), { status: 0 });

    expect(componente.error()).toContain('connection');
  });

  it('warns when the previous session expired', () => {
    const { fixture } = crearComponente({ expirada: 'true' });
    expect(fixture.componentInstance.sesionExpirada()).toBeTrue();
  });
});
