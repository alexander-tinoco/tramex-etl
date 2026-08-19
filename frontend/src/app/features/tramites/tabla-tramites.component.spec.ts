import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TablaTramitesComponent } from './tabla-tramites.component';
import { MasterTramex, Paginado } from '../../models/api.model';
import { RECURSOS } from '../../models/recursos.model';

function registro(id: number, nombre = `Cliente ${id}`, archivado = false): MasterTramex {
  return {
    id,
    cliente_id: id,
    nombre,
    id_solicitud: `SOL${id}`,
    telefono: null,
    numero_pasaporte: `G${id}`,
    tramite: 'VISA B1/B2',
    cita: null,
    correo_electronico: null,
    cargado_en: '2026-08-17T10:00:00',
    actualizado_en: '2026-08-17T10:00:00',
    eliminado_en: archivado ? '2026-08-17T12:00:00' : null,
  };
}

function pagina(items: MasterTramex[], total = items.length): Paginado<MasterTramex> {
  return { total, skip: 0, limit: 10, items };
}

describe('TablaTramitesComponent', () => {
  let fixture: ComponentFixture<TablaTramitesComponent>;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [TablaTramitesComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    fixture = TestBed.createComponent(TablaTramitesComponent);
    fixture.componentRef.setInput('recurso', RECURSOS['master_tramex']);
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
  });

  afterEach(() => TestBed.resetTestingModule());

  function responderListado(datos = pagina([registro(1), registro(2)])): void {
    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(datos);
    fixture.detectChanges();
  }

  it('loads the resource records on startup', () => {
    responderListado();
    expect(fixture.componentInstance.registros().length).toBe(2);
    expect(fixture.componentInstance.total()).toBe(2);
    http.verify();
  });

  it('shows a message when the load fails', () => {
    http
      .expectOne((r) => r.url === '/api/v1/master-tramex/')
      .flush(null, { status: 500, statusText: 'Error' });
    fixture.detectChanges();

    expect(fixture.componentInstance.error()).toBeTruthy();
    expect(fixture.componentInstance.cargando()).toBeFalse();
    http.verify();
  });

  it('groups search keystrokes into a single request', fakeAsync(() => {
    responderListado();

    const componente = fixture.componentInstance;
    const evento = (valor: string): Event =>
      ({ target: { value: valor } }) as unknown as Event;

    // Without the delay, every keystroke would fire a request to the backend.
    componente.buscar(evento('j'));
    componente.buscar(evento('jo'));
    componente.buscar(evento('jorge'));
    tick(300);

    const peticiones = http.match((r) => r.url === '/api/v1/master-tramex/');
    expect(peticiones.length).toBe(1);
    expect(peticiones[0].request.params.get('buscar')).toBe('jorge');
    peticiones[0].flush(pagina([registro(1, 'Jorge Monroy')]));

    http.verify();
  }));

  it('a search goes back to the first page', fakeAsync(() => {
    responderListado(pagina([registro(1)], 40));

    fixture.componentInstance.paginaSiguiente();
    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([registro(11)], 40));
    expect(fixture.componentInstance.pagina()).toBe(1);

    fixture.componentInstance.buscar({ target: { value: 'ana' } } as unknown as Event);
    tick(300);
    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([], 0));

    expect(fixture.componentInstance.pagina()).toBe(0);
    http.verify();
  }));

  it('does not advance past the last page', () => {
    responderListado(pagina([registro(1)], 5));

    fixture.componentInstance.paginaSiguiente();

    expect(fixture.componentInstance.pagina()).toBe(0);
    expect(fixture.componentInstance.hayPaginaSiguiente()).toBeFalse();
    http.verify();
  });

  it('computes the total number of pages', () => {
    responderListado(pagina([registro(1)], 25));
    expect(fixture.componentInstance.totalPaginas()).toBe(3);
    http.verify();
  });

  it('requests archived records only when asked for', () => {
    responderListado();

    fixture.componentInstance.alternarArchivados();
    const peticion = http.expectOne((r) => r.url === '/api/v1/master-tramex/');
    expect(peticion.request.params.get('incluir_eliminados')).toBe('true');
    peticion.flush(pagina([registro(1, 'Cliente 1', true)]));

    expect(fixture.componentInstance.estaArchivado(registro(1, 'x', true))).toBeTrue();
    http.verify();
  });

  it('archiving uses DELETE and reloads the list', () => {
    responderListado();

    fixture.componentInstance.confirmarArchivado(registro(1));
    fixture.componentInstance.archivar();

    const borrado = http.expectOne('/api/v1/master-tramex/1');
    expect(borrado.request.method).toBe('DELETE');
    borrado.flush(null);

    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([registro(2)]));
    expect(fixture.componentInstance.registroAArchivar()).toBeNull();
    http.verify();
  });

  it('restoring reactivates the record', () => {
    responderListado();

    fixture.componentInstance.restaurar(registro(1, 'Cliente 1', true));
    http.expectOne('/api/v1/master-tramex/1/restaurar').flush(registro(1));
    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([registro(1)]));

    http.verify();
  });

  it('saving in create mode does a POST', () => {
    responderListado();

    fixture.componentInstance.abrirAlta();
    fixture.componentInstance.guardar({ nombre: 'Nueva Persona' });

    const creacion = http.expectOne('/api/v1/master-tramex/');
    expect(creacion.request.method).toBe('POST');
    creacion.flush(registro(3, 'Nueva Persona'));

    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([registro(3)]));
    expect(fixture.componentInstance.formularioAbierto()).toBeFalse();
    http.verify();
  });

  it('saving in edit mode does a PATCH', () => {
    responderListado();

    fixture.componentInstance.abrirEdicion(registro(1));
    fixture.componentInstance.guardar({ nombre: 'Nombre Corregido' });

    const edicion = http.expectOne('/api/v1/master-tramex/1');
    expect(edicion.request.method).toBe('PATCH');
    edicion.flush(registro(1, 'Nombre Corregido'));

    http.expectOne((r) => r.url === '/api/v1/master-tramex/').flush(pagina([registro(1)]));
    http.verify();
  });

  it('a 422 while saving leaves the form open with the reason', () => {
    responderListado();

    fixture.componentInstance.abrirAlta();
    fixture.componentInstance.guardar({ nombre: '' });

    http
      .expectOne('/api/v1/master-tramex/')
      .flush({ detail: 'invalid' }, { status: 422, statusText: 'Unprocessable' });

    expect(fixture.componentInstance.formularioAbierto()).toBeTrue();
    expect(fixture.componentInstance.errorFormulario()).toContain('format');
    http.verify();
  });
});
