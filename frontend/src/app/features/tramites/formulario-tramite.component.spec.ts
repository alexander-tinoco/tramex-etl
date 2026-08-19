import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormularioTramiteComponent } from './formulario-tramite.component';
import { CuerpoTramite, MasterTramex } from '../../models/api.model';
import { RECURSOS } from '../../models/recursos.model';

const REGISTRO: MasterTramex = {
  id: 3,
  cliente_id: 1,
  nombre: 'Jorge Monroy',
  id_solicitud: 'SOL777',
  telefono: '4471148272',
  numero_pasaporte: 'G33961340',
  tramite: 'VISA B1/B2',
  cita: null,
  correo_electronico: 'jorge@example.com',
  cargado_en: '2026-08-17T10:00:00',
  actualizado_en: '2026-08-17T10:00:00',
  eliminado_en: null,
};

async function montar(registro: MasterTramex | null): Promise<{
  fixture: ComponentFixture<FormularioTramiteComponent>;
  emitido: CuerpoTramite[];
}> {
  TestBed.configureTestingModule({ imports: [FormularioTramiteComponent] });
  const fixture = TestBed.createComponent(FormularioTramiteComponent);
  fixture.componentRef.setInput('recurso', RECURSOS['master_tramex']);
  fixture.componentRef.setInput('registro', registro);
  fixture.detectChanges();

  const emitido: CuerpoTramite[] = [];
  fixture.componentInstance.guardar.subscribe((cuerpo) => emitido.push(cuerpo));

  // The preload happens in a microtask, so the inputs need to be resolved first.
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, emitido };
}

describe('FormularioTramiteComponent', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('on a new record it starts with empty fields', async () => {
    const { fixture } = await montar(null);
    expect(fixture.componentInstance.esEdicion()).toBeFalse();
    expect(fixture.componentInstance.valores()['nombre']).toBe('');
  });

  it('when editing it preloads the record values', async () => {
    const { fixture } = await montar(REGISTRO);
    expect(fixture.componentInstance.esEdicion()).toBeTrue();
    expect(fixture.componentInstance.valores()['nombre']).toBe('Jorge Monroy');
    expect(fixture.componentInstance.valores()['id_solicitud']).toBe('SOL777');
  });

  it('never preloads the credential', async () => {
    // The API does not return it on reads; leaving the field empty communicates
    // the right thing: it's only overwritten if something is typed into it.
    const { fixture } = await montar(REGISTRO);
    expect(fixture.componentInstance.valores()['contrasena']).toBe('');
  });

  it('an empty password field is not sent, so the credential is not erased', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido.length).toBe(1);
    expect('contrasena' in emitido[0]).toBeFalse();
  });

  it('a typed password is sent', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.actualizarCampo('contrasena', 'new-credential');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['contrasena']).toBe('new-credential');
  });

  it('when editing, a field cleared out is sent as null so the API erases it', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.actualizarCampo('telefono', '   ');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['telefono']).toBeNull();
  });

  it('on a new record, empty fields are omitted instead of sent as null', async () => {
    const { fixture, emitido } = await montar(null);
    fixture.componentInstance.actualizarCampo('nombre', 'Ana Lopez');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['nombre']).toBe('Ana Lopez');
    expect('telefono' in emitido[0]).toBeFalse();
  });

  it('trims whitespace from values', async () => {
    const { fixture, emitido } = await montar(null);
    fixture.componentInstance.actualizarCampo('nombre', '  Ana Lopez  ');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['nombre']).toBe('Ana Lopez');
  });
});
