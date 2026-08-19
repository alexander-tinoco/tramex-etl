/**
 * API contracts.
 *
 * These types mirror the backend's Pydantic schemas. They exist because the
 * HTTP service used to return `any` from every method: the project used
 * TypeScript without getting anything from TypeScript, and a contract change
 * in the API was only discovered at runtime.
 */

/** Wrapper for any paginated listing. */
export interface Paginado<T> {
  total: number;
  skip: number;
  limit: number;
  items: T[];
}

/** Administrative fields common to every record the API returns. */
export interface RegistroBase {
  id: number;
  cargado_en: string;
  actualizado_en: string;
  /** Soft-delete marker. Null while the record is active. */
  eliminado_en: string | null;
}

export interface Cliente extends RegistroBase {
  nombre: string;
  apellido: string | null;
  correo_electronico: string | null;
  telefono: string | null;
  numero_pasaporte: string | null;
}

export interface ClienteDetalle extends Cliente {
  /** Count of active tramites per table. */
  tramites: Record<string, number>;
}

interface TramiteBase extends RegistroBase {
  /** Person the tramite belongs to. */
  cliente_id: number;
  nombre: string;
}

export interface MasterTramex extends TramiteBase {
  id_solicitud: string | null;
  telefono: string | null;
  numero_pasaporte: string | null;
  tramite: string | null;
  cita: string | null;
  correo_electronico: string | null;
}

export interface GlobalEntry extends TramiteBase {
  apellido: string | null;
  correo_electronico: string | null;
  numero_pasaporte: string | null;
}

export interface Pasaporte extends TramiteBase {
  apellido: string | null;
  telefono: string | null;
  lugar_cita: string | null;
  fecha_cita: string | null;
  /**
   * Original text of the cell when it was not a valid date. The source file
   * contains values such as "MARCH", which the pipeline preserves instead of
   * discarding.
   */
  fecha_cita_original: string | null;
}

export interface Canada extends TramiteBase {
  cuenta_ircc: string | null;
  telefono: string | null;
  numero_pasaporte: string | null;
}

/** Any of the four tramite types. */
export type Tramite = MasterTramex | GlobalEntry | Pasaporte | Canada;

/**
 * Body accepted when creating or editing a tramite.
 *
 * Modeled as a record of primitive values because the form is generic over
 * the four resources; `unknown` would force a cast on every read without
 * adding real type safety.
 */
export type CuerpoTramite = Record<string, string | number | null>;

export type Rol = 'admin' | 'operador';

export interface Usuario {
  id: number;
  correo_electronico: string;
  nombre: string;
  rol: Rol;
  activo: boolean;
  ultimo_acceso_en: string | null;
  cargado_en: string;
}

export interface RespuestaToken {
  access_token: string;
  token_type: string;
  expira_en_minutos: number;
  usuario: Usuario;
}

/** Result of the audited decryption endpoint. */
export interface RespuestaCredencial {
  contrasena: string | null;
  registro_id: number;
  recurso: string;
  /** Audit-log entry the query left behind. */
  auditoria_id: number;
}

export type NivelAuditoria = 'INFO' | 'ADVERTENCIA' | 'ALERTA';

export interface AsientoAuditoria {
  id: number;
  ocurrido_en: string;
  usuario_id: number | null;
  usuario_correo: string | null;
  accion: string;
  recurso: string | null;
  registro_id: number | null;
  cliente_id: number | null;
  nivel: NivelAuditoria;
  direccion_ip: string | null;
  detalle: string | null;
}

export interface EstadoSalud {
  status: string;
  database: string;
  version: string;
}
