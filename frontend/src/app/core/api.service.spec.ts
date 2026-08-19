import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ApiService } from './api.service';
import { MasterTramex } from '../models/api.model';

describe('ApiService', () => {
  let servicio: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    servicio = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('paginates with skip and limit', () => {
    servicio.listar<MasterTramex>('/master-tramex/', { skip: 20, limit: 10 }).subscribe();

    const peticion = http.expectOne((r) => r.url === '/api/v1/master-tramex/');
    expect(peticion.request.params.get('skip')).toBe('20');
    expect(peticion.request.params.get('limit')).toBe('10');
    peticion.flush({ total: 0, skip: 20, limit: 10, items: [] });
  });

  it('omits the search parameter when empty', () => {
    servicio.listar('/canada/', { buscar: undefined }).subscribe();

    const peticion = http.expectOne((r) => r.url === '/api/v1/canada/');
    expect(peticion.request.params.has('buscar')).toBeFalse();
    peticion.flush({ total: 0, skip: 0, limit: 10, items: [] });
  });

  it('encodes the search term', () => {
    servicio.listar('/canada/', { buscar: 'José Ramírez' }).subscribe();

    const peticion = http.expectOne((r) => r.url === '/api/v1/canada/');
    expect(peticion.request.params.get('buscar')).toBe('José Ramírez');
    peticion.flush({ total: 0, skip: 0, limit: 10, items: [] });
  });

  it('explicitly requests archived records when asked for', () => {
    servicio.listar('/pasaportes/', { incluirEliminados: true }).subscribe();

    const peticion = http.expectOne((r) => r.url === '/api/v1/pasaportes/');
    expect(peticion.request.params.get('incluir_eliminados')).toBe('true');
    peticion.flush({ total: 0, skip: 0, limit: 10, items: [] });
  });

  it('deleting uses DELETE, which in the API is a soft delete', () => {
    servicio.archivar('/master-tramex/', 7).subscribe();

    const peticion = http.expectOne('/api/v1/master-tramex/7');
    expect(peticion.request.method).toBe('DELETE');
    peticion.flush(null);
  });

  it('the credential lookup returns the audit-log entry', (done) => {
    servicio.obtenerCredencial('/canada/', 3).subscribe((respuesta) => {
      expect(respuesta.contrasena).toBe('client-secret');
      expect(respuesta.auditoria_id).toBe(42);
      done();
    });

    http.expectOne('/api/v1/canada/3/password').flush({
      contrasena: 'client-secret',
      registro_id: 3,
      recurso: 'Canada',
      auditoria_id: 42,
    });
  });

  it('every request travels with credentials', () => {
    servicio.listar('/canada/').subscribe();
    const peticion = http.expectOne((r) => r.url === '/api/v1/canada/');
    expect(peticion.request.withCredentials).toBeTrue();
    peticion.flush({ total: 0, skip: 0, limit: 10, items: [] });
  });
});
