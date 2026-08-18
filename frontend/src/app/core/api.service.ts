import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AsientoAuditoria,
  ClienteDetalle,
  CuerpoTramite,
  EstadoSalud,
  Paginado,
  RespuestaCredencial,
  Tramite,
} from '../models/api.model';

/** Filtros aceptados por los listados de tramites. */
export interface FiltrosListado {
  skip?: number;
  limit?: number;
  buscar?: string;
  clienteId?: number;
  incluirEliminados?: boolean;
}

/**
 * Cliente HTTP de la API.
 *
 * Todos los metodos son genericos y tipados: la version anterior devolvia
 * `any` en cada uno, lo que anulaba cualquier comprobacion de tipos sobre las
 * respuestas del backend.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  /** Las peticiones llevan la cookie de sesion; sin esto la API responde 401. */
  private readonly opciones = { withCredentials: true } as const;

  estadoSalud(): Observable<EstadoSalud> {
    return this.http.get<EstadoSalud>(environment.healthUrl, this.opciones);
  }

  listar<T extends Tramite>(endpoint: string, filtros: FiltrosListado = {}): Observable<Paginado<T>> {
    let params = new HttpParams()
      .set('skip', String(filtros.skip ?? 0))
      .set('limit', String(filtros.limit ?? 10));

    if (filtros.buscar) {
      params = params.set('buscar', filtros.buscar);
    }
    if (filtros.clienteId !== undefined) {
      params = params.set('cliente_id', String(filtros.clienteId));
    }
    if (filtros.incluirEliminados) {
      params = params.set('incluir_eliminados', 'true');
    }

    return this.http.get<Paginado<T>>(`${this.baseUrl}${endpoint}`, { ...this.opciones, params });
  }

  crear<T extends Tramite>(endpoint: string, cuerpo: CuerpoTramite): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${endpoint}`, cuerpo, this.opciones);
  }

  actualizar<T extends Tramite>(endpoint: string, id: number, cuerpo: CuerpoTramite): Observable<T> {
    return this.http.patch<T>(`${this.baseUrl}${endpoint}${id}`, cuerpo, this.opciones);
  }

  /** Baja logica: el registro se conserva y puede restaurarse. */
  archivar(endpoint: string, id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}${endpoint}${id}`, this.opciones);
  }

  restaurar<T extends Tramite>(endpoint: string, id: number): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${endpoint}${id}/restaurar`, {}, this.opciones);
  }

  /**
   * Descifra la credencial de un registro.
   *
   * Es la operacion mas sensible de la API: cada llamada queda asentada en la
   * bitacora de auditoria, y la respuesta incluye el identificador del asiento.
   */
  obtenerCredencial(endpoint: string, id: number): Observable<RespuestaCredencial> {
    return this.http.get<RespuestaCredencial>(
      `${this.baseUrl}${endpoint}${id}/password`,
      this.opciones,
    );
  }

  obtenerCliente(id: number): Observable<ClienteDetalle> {
    return this.http.get<ClienteDetalle>(`${this.baseUrl}/clientes/${id}`, this.opciones);
  }

  listarAuditoria(skip = 0, limit = 25, accion?: string): Observable<Paginado<AsientoAuditoria>> {
    let params = new HttpParams().set('skip', String(skip)).set('limit', String(limit));
    if (accion) {
      params = params.set('accion', accion);
    }
    return this.http.get<Paginado<AsientoAuditoria>>(`${this.baseUrl}/admin/auditoria`, {
      ...this.opciones,
      params,
    });
  }
}
