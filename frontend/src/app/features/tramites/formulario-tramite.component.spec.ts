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

  // La precarga ocurre en un microtask para que las entradas ya esten resueltas.
  await fixture.whenStable();
  fixture.detectChanges();
  return { fixture, emitido };
}

describe('FormularioTramiteComponent', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('en un alta arranca con los campos vacíos', async () => {
    const { fixture } = await montar(null);
    expect(fixture.componentInstance.esEdicion()).toBeFalse();
    expect(fixture.componentInstance.valores()['nombre']).toBe('');
  });

  it('en edición precarga los valores del registro', async () => {
    const { fixture } = await montar(REGISTRO);
    expect(fixture.componentInstance.esEdicion()).toBeTrue();
    expect(fixture.componentInstance.valores()['nombre']).toBe('Jorge Monroy');
    expect(fixture.componentInstance.valores()['id_solicitud']).toBe('SOL777');
  });

  it('nunca precarga la credencial', async () => {
    // La API no la devuelve en las lecturas; dejar el campo vacio comunica lo
    // correcto: solo se sobrescribe si se escribe algo.
    const { fixture } = await montar(REGISTRO);
    expect(fixture.componentInstance.valores()['contrasena']).toBe('');
  });

  it('un campo de contraseña vacío no se envía, para no borrar la credencial', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido.length).toBe(1);
    expect('contrasena' in emitido[0]).toBeFalse();
  });

  it('una contraseña escrita sí se envía', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.actualizarCampo('contrasena', 'nueva-credencial');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['contrasena']).toBe('nueva-credencial');
  });

  it('en edición un campo vaciado se envía como null para que la API lo borre', async () => {
    const { fixture, emitido } = await montar(REGISTRO);
    fixture.componentInstance.actualizarCampo('telefono', '   ');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['telefono']).toBeNull();
  });

  it('en un alta los campos vacíos se omiten en vez de enviarse como null', async () => {
    const { fixture, emitido } = await montar(null);
    fixture.componentInstance.actualizarCampo('nombre', 'Ana Lopez');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['nombre']).toBe('Ana Lopez');
    expect('telefono' in emitido[0]).toBeFalse();
  });

  it('recorta los espacios de los valores', async () => {
    const { fixture, emitido } = await montar(null);
    fixture.componentInstance.actualizarCampo('nombre', '  Ana Lopez  ');
    fixture.componentInstance.enviar(new Event('submit'));

    expect(emitido[0]['nombre']).toBe('Ana Lopez');
  });
});
