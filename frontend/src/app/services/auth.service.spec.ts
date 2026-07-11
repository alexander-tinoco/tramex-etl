import { TestBed } from '@angular/core/testing';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(AuthService);
    // Limpiar localStorage antes de cada prueba
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('debe crearse correctamente', () => {
    expect(service).toBeTruthy();
  });

  it('debe guardar el token en localStorage', () => {
    const testToken = 'fake-jwt-token-xyz';
    service.setToken(testToken);
    expect(localStorage.getItem('tramex_token')).toBe(testToken);
  });

  it('debe obtener el token desde localStorage', () => {
    const testToken = 'fake-jwt-token-123';
    localStorage.setItem('tramex_token', testToken);
    expect(service.getToken()).toBe(testToken);
  });

  it('debe remover el token al cerrar sesión (logout)', () => {
    localStorage.setItem('tramex_token', 'active-token');
    service.logout();
    expect(localStorage.getItem('tramex_token')).toBeNull();
  });

  it('debe retornar true en isLoggedIn si existe un token', () => {
    localStorage.setItem('tramex_token', 'active-token');
    expect(service.isLoggedIn()).toBeTrue();
  });

  it('debe retornar false en isLoggedIn si no existe un token', () => {
    expect(service.isLoggedIn()).toBeFalse();
  });
});
