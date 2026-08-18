/**
 * Contratos de la API.
 *
 * Estos tipos son el reflejo de los esquemas Pydantic del backend. Existen
 * porque antes el servicio HTTP devolvia `any` en todos sus metodos: el
 * proyecto usaba TypeScript sin obtener nada de TypeScript, y un cambio de
 * contrato en la API solo se descubria en tiempo de ejecucion.
 */

/** Envoltorio de cualquier listado paginado. */
export interface Paginado<T> {
  total: number;
  skip: number;
  limit: number;
  items: T[];
}

/** Campos administrativos comunes a todo registro devuelto por la API. */
export interface RegistroBase {
  id: number;
  cargado_en: string;
  actualizado_en: string;
  /** Marca de baja logica. Nulo mientras el registro esta vigente. */
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
  /** Conteo de tramites activos por tabla. */
  tramites: Record<string, number>;
}

interface TramiteBase extends RegistroBase {
  /** Persona a la que pertenece el tramite. */
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
   * Texto original de la celda cuando no era una fecha valida. El archivo de
   * origen contiene valores como "MARZO", que el pipeline preserva en vez de
   * descartar.
   */
  fecha_cita_original: string | null;
}

export interface Canada extends TramiteBase {
  cuenta_ircc: string | null;
  telefono: string | null;
  numero_pasaporte: string | null;
}

/** Cualquiera de los cuatro tipos de tramite. */
export type Tramite = MasterTramex | GlobalEntry | Pasaporte | Canada;

/**
 * Cuerpo aceptado al crear o editar un tramite.
 *
 * Se modela como registro de valores primitivos porque el formulario es
 * generico sobre los cuatro recursos; `unknown` obligaria a un casteo en cada
 * lectura sin aportar seguridad real.
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

/** Resultado del endpoint auditado de descifrado. */
export interface RespuestaCredencial {
  contrasena: string | null;
  registro_id: number;
  recurso: string;
  /** Asiento que dejo la consulta en la bitacora de auditoria. */
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
