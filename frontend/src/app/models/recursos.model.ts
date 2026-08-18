/**
 * Configuracion declarativa de los cuatro recursos de tramite.
 *
 * La tabla, el formulario y las acciones se generan a partir de esta
 * descripcion en lugar de existir cuatro veces en la plantilla. Anadir una
 * columna o un campo es tocar este archivo, no cuatro bloques de HTML.
 */

/** Tipo de control con el que se captura un campo. */
export type TipoCampo = 'text' | 'email' | 'tel' | 'date' | 'password';

export interface CampoRecurso {
  nombre: string;
  etiqueta: string;
  tipo: TipoCampo;
  requerido?: boolean;
  /** Ocupa el ancho completo del formulario en lugar de media columna. */
  anchoCompleto?: boolean;
  ayuda?: string;
}

export interface ColumnaRecurso {
  campo: string;
  etiqueta: string;
  /** Formato aplicado al mostrar el valor en la tabla. */
  formato?: 'texto' | 'fecha' | 'fechaHora';
}

export interface ConfiguracionRecurso {
  clave: ClaveRecurso;
  titulo: string;
  icono: string;
  /** Segmento de la API, ya con las barras que espera el backend. */
  endpoint: string;
  /** Si el recurso custodia una credencial cifrada del cliente. */
  tieneCredencial: boolean;
  columnas: ColumnaRecurso[];
  campos: CampoRecurso[];
}

export type ClaveRecurso = 'master_tramex' | 'global_entry' | 'pasaportes' | 'canada';

export const RECURSOS: Record<ClaveRecurso, ConfiguracionRecurso> = {
  master_tramex: {
    clave: 'master_tramex',
    titulo: 'Master Tramex',
    icono: 'fa-list-check',
    endpoint: '/master-tramex/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Nombre' },
      { campo: 'id_solicitud', etiqueta: 'ID Solicitud' },
      { campo: 'telefono', etiqueta: 'Teléfono' },
      { campo: 'numero_pasaporte', etiqueta: 'Pasaporte' },
      { campo: 'tramite', etiqueta: 'Trámite' },
      { campo: 'cita', etiqueta: 'Cita' },
      { campo: 'correo_electronico', etiqueta: 'Correo' },
      { campo: 'cargado_en', etiqueta: 'Cargado', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre completo', tipo: 'text', requerido: true, anchoCompleto: true },
      { nombre: 'id_solicitud', etiqueta: 'ID de solicitud', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'tel' },
      { nombre: 'numero_pasaporte', etiqueta: 'Número de pasaporte', tipo: 'text' },
      { nombre: 'correo_electronico', etiqueta: 'Correo electrónico', tipo: 'email' },
      { nombre: 'tramite', etiqueta: 'Tipo de trámite', tipo: 'text' },
      { nombre: 'cita', etiqueta: 'Estado o fecha de la cita', tipo: 'text' },
      {
        nombre: 'contrasena',
        etiqueta: 'Contraseña de la cuenta',
        tipo: 'password',
        anchoCompleto: true,
        ayuda: 'Se cifra antes de guardarse y nunca se devuelve en los listados.',
      },
    ],
  },
  global_entry: {
    clave: 'global_entry',
    titulo: 'Global Entry',
    icono: 'fa-globe',
    endpoint: '/global-entry/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Nombre' },
      { campo: 'apellido', etiqueta: 'Apellido' },
      { campo: 'correo_electronico', etiqueta: 'Correo' },
      { campo: 'numero_pasaporte', etiqueta: 'Pasaporte' },
      { campo: 'cargado_en', etiqueta: 'Cargado', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
      { nombre: 'apellido', etiqueta: 'Apellido', tipo: 'text' },
      { nombre: 'correo_electronico', etiqueta: 'Correo electrónico', tipo: 'email', anchoCompleto: true },
      { nombre: 'numero_pasaporte', etiqueta: 'Número de pasaporte', tipo: 'text' },
      {
        nombre: 'contrasena',
        etiqueta: 'Contraseña de la cuenta',
        tipo: 'password',
        ayuda: 'En el archivo de origen esta columna se llamaba "Número de la cuenta".',
      },
    ],
  },
  pasaportes: {
    clave: 'pasaportes',
    titulo: 'Pasaportes',
    icono: 'fa-book-bookmark',
    endpoint: '/pasaportes/',
    tieneCredencial: false,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Nombre' },
      { campo: 'apellido', etiqueta: 'Apellido' },
      { campo: 'telefono', etiqueta: 'Teléfono' },
      { campo: 'lugar_cita', etiqueta: 'Lugar de cita' },
      { campo: 'fecha_cita', etiqueta: 'Fecha de cita', formato: 'fecha' },
      { campo: 'fecha_cita_original', etiqueta: 'Texto original' },
      { campo: 'cargado_en', etiqueta: 'Cargado', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre', tipo: 'text', requerido: true },
      { nombre: 'apellido', etiqueta: 'Apellido', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'tel' },
      { nombre: 'lugar_cita', etiqueta: 'Lugar de la cita', tipo: 'text' },
      { nombre: 'fecha_cita', etiqueta: 'Fecha de la cita', tipo: 'date' },
      {
        nombre: 'fecha_cita_original',
        etiqueta: 'Fecha como texto libre',
        tipo: 'text',
        anchoCompleto: true,
        ayuda: 'Para citas sin fecha exacta, como "MARZO" o "pendiente".',
      },
    ],
  },
  canada: {
    clave: 'canada',
    titulo: 'Canadá',
    icono: 'fa-map',
    endpoint: '/canada/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Nombre' },
      { campo: 'cuenta_ircc', etiqueta: 'Cuenta IRCC' },
      { campo: 'telefono', etiqueta: 'Teléfono' },
      { campo: 'numero_pasaporte', etiqueta: 'Pasaporte' },
      { campo: 'cargado_en', etiqueta: 'Cargado', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Nombre completo', tipo: 'text', requerido: true, anchoCompleto: true },
      { nombre: 'cuenta_ircc', etiqueta: 'Cuenta IRCC', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Teléfono', tipo: 'tel' },
      { nombre: 'numero_pasaporte', etiqueta: 'Número de pasaporte', tipo: 'text' },
      { nombre: 'contrasena', etiqueta: 'Contraseña de la cita', tipo: 'password' },
    ],
  },
};

/** Orden en el que se muestran los recursos en la navegación. */
export const CLAVES_RECURSO: ClaveRecurso[] = ['master_tramex', 'global_entry', 'pasaportes', 'canada'];
