import { NombrePictograma } from '../shared/pictograma.component';

/**
 * Declarative configuration of the four tramite resources.
 *
 * The table, the form and the actions are generated from this description
 * instead of existing four times in the template. Adding a column or a field
 * means touching this file, not four blocks of HTML.
 */

/** Control type used to capture a field. */
export type TipoCampo = 'text' | 'email' | 'tel' | 'date' | 'password';

export interface CampoRecurso {
  nombre: string;
  etiqueta: string;
  tipo: TipoCampo;
  requerido?: boolean;
  /** Spans the full form width instead of half a column. */
  anchoCompleto?: boolean;
  ayuda?: string;
}

export interface ColumnaRecurso {
  campo: string;
  etiqueta: string;
  /** Format applied when displaying the value in the table. */
  formato?: 'texto' | 'fecha' | 'fechaHora';
}

export interface ConfiguracionRecurso {
  clave: ClaveRecurso;
  titulo: string;
  /** Lane pictogram, from the system's own icon repertoire. */
  picto: NombrePictograma;
  /** What this tramite is, in one line, for the section header. */
  descripcion: string;
  /** API segment, already with the slashes the backend expects. */
  endpoint: string;
  /** Whether the resource holds an encrypted client credential. */
  tieneCredencial: boolean;
  columnas: ColumnaRecurso[];
  campos: CampoRecurso[];
}

export type ClaveRecurso = 'master_tramex' | 'global_entry' | 'pasaportes' | 'canada';

export const RECURSOS: Record<ClaveRecurso, ConfiguracionRecurso> = {
  master_tramex: {
    clave: 'master_tramex',
    titulo: 'Master Tramex',
    picto: 'visa',
    descripcion: 'US visas and related tramites. Holds the credential for the client\'s consular account.',
    endpoint: '/master-tramex/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Name' },
      { campo: 'id_solicitud', etiqueta: 'Application ID' },
      { campo: 'telefono', etiqueta: 'Phone' },
      { campo: 'numero_pasaporte', etiqueta: 'Passport' },
      { campo: 'tramite', etiqueta: 'Tramite' },
      { campo: 'cita', etiqueta: 'Appointment' },
      { campo: 'correo_electronico', etiqueta: 'Email' },
      { campo: 'cargado_en', etiqueta: 'Loaded', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Full name', tipo: 'text', requerido: true, anchoCompleto: true },
      { nombre: 'id_solicitud', etiqueta: 'Application ID', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Phone', tipo: 'tel' },
      { nombre: 'numero_pasaporte', etiqueta: 'Passport number', tipo: 'text' },
      { nombre: 'correo_electronico', etiqueta: 'Email address', tipo: 'email' },
      { nombre: 'tramite', etiqueta: 'Tramite type', tipo: 'text' },
      { nombre: 'cita', etiqueta: 'Appointment status or date', tipo: 'text' },
      {
        nombre: 'contrasena',
        etiqueta: 'Account password',
        tipo: 'password',
        anchoCompleto: true,
        ayuda: 'Encrypted before saving and never returned in listings.',
      },
    ],
  },
  global_entry: {
    clave: 'global_entry',
    titulo: 'Global Entry',
    picto: 'globo',
    descripcion: 'Trusted traveler program. The "Account number" column in the original file is actually the credential.',
    endpoint: '/global-entry/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Name' },
      { campo: 'apellido', etiqueta: 'Last name' },
      { campo: 'correo_electronico', etiqueta: 'Email' },
      { campo: 'numero_pasaporte', etiqueta: 'Passport' },
      { campo: 'cargado_en', etiqueta: 'Loaded', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Name', tipo: 'text', requerido: true },
      { nombre: 'apellido', etiqueta: 'Last name', tipo: 'text' },
      { nombre: 'correo_electronico', etiqueta: 'Email address', tipo: 'email', anchoCompleto: true },
      { nombre: 'numero_pasaporte', etiqueta: 'Passport number', tipo: 'text' },
      {
        nombre: 'contrasena',
        etiqueta: 'Account password',
        tipo: 'password',
        ayuda: 'In the source file this column was called "Account number".',
      },
    ],
  },
  pasaportes: {
    clave: 'pasaportes',
    titulo: 'Passports',
    picto: 'pasaporte',
    descripcion: 'Passport issuance and renewal appointments. The only sheet with no credentials and no hard identifier.',
    endpoint: '/pasaportes/',
    tieneCredencial: false,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Name' },
      { campo: 'apellido', etiqueta: 'Last name' },
      { campo: 'telefono', etiqueta: 'Phone' },
      { campo: 'lugar_cita', etiqueta: 'Appointment location' },
      { campo: 'fecha_cita', etiqueta: 'Appointment date', formato: 'fecha' },
      { campo: 'fecha_cita_original', etiqueta: 'Original text' },
      { campo: 'cargado_en', etiqueta: 'Loaded', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Name', tipo: 'text', requerido: true },
      { nombre: 'apellido', etiqueta: 'Last name', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Phone', tipo: 'tel' },
      { nombre: 'lugar_cita', etiqueta: 'Appointment location', tipo: 'text' },
      { nombre: 'fecha_cita', etiqueta: 'Appointment date', tipo: 'date' },
      {
        nombre: 'fecha_cita_original',
        etiqueta: 'Date as free text',
        tipo: 'text',
        anchoCompleto: true,
        ayuda: 'For appointments without an exact date, such as "MARCH" or "pending".',
      },
    ],
  },
  canada: {
    clave: 'canada',
    titulo: 'Canada',
    picto: 'hoja',
    descripcion: 'Tramites with an IRCC account. The "Appointment account" column in the original file is the credential.',
    endpoint: '/canada/',
    tieneCredencial: true,
    columnas: [
      { campo: 'id', etiqueta: 'ID' },
      { campo: 'nombre', etiqueta: 'Name' },
      { campo: 'cuenta_ircc', etiqueta: 'IRCC account' },
      { campo: 'telefono', etiqueta: 'Phone' },
      { campo: 'numero_pasaporte', etiqueta: 'Passport' },
      { campo: 'cargado_en', etiqueta: 'Loaded', formato: 'fecha' },
    ],
    campos: [
      { nombre: 'nombre', etiqueta: 'Full name', tipo: 'text', requerido: true, anchoCompleto: true },
      { nombre: 'cuenta_ircc', etiqueta: 'IRCC account', tipo: 'text' },
      { nombre: 'telefono', etiqueta: 'Phone', tipo: 'tel' },
      { nombre: 'numero_pasaporte', etiqueta: 'Passport number', tipo: 'text' },
      { nombre: 'contrasena', etiqueta: 'Appointment password', tipo: 'password' },
    ],
  },
};

/** Order in which resources are shown in the navigation. */
export const CLAVES_RECURSO: ClaveRecurso[] = ['master_tramex', 'global_entry', 'pasaportes', 'canada'];
