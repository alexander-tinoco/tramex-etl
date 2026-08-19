import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  AsientoAuditoria,
  Cliente,
  ClienteDetalle,
  CuerpoTramite,
  EstadoSalud,
  Paginado,
  RespuestaCredencial,
  Tramite,
} from '../models/api.model';

/** Filters accepted by the tramite listings. */
export interface FiltrosListado {
  skip?: number;
  limit?: number;
  buscar?: string;
  clienteId?: number;
  incluirEliminados?: boolean;
  /** `reciente` returns the most recently touched records first; used by the floor's board. */
  orden?: 'id' | 'reciente';
}

/**
 * HTTP client for the API.
 *
 * Every method is generic and typed: the previous version returned `any`
 * from all of them, which nullified any type checking on the backend's
 * responses.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  /** Requests carry the session cookie; without this the API responds 401. */
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
    if (filtros.orden) {
      params = params.set('orden', filtros.orden);
    }

    return this.http.get<Paginado<T>>(`${this.baseUrl}${endpoint}`, { ...this.opciones, params });
  }

  crear<T extends Tramite>(endpoint: string, cuerpo: CuerpoTramite): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${endpoint}`, cuerpo, this.opciones);
  }

  actualizar<T extends Tramite>(endpoint: string, id: number, cuerpo: CuerpoTramite): Observable<T> {
    return this.http.patch<T>(`${this.baseUrl}${endpoint}${id}`, cuerpo, this.opciones);
  }

  /** Soft delete: the record is kept and can be restored. */
  archivar(endpoint: string, id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}${endpoint}${id}`, this.opciones);
  }

  restaurar<T extends Tramite>(endpoint: string, id: number): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${endpoint}${id}/restaurar`, {}, this.opciones);
  }

  /**
   * Decrypts a record's credential.
   *
   * It's the most sensitive operation in the API: every call is logged in
   * the audit trail, and the response includes the identifier of that entry.
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

  /**
   * Searches for people, not rows.
   *
   * The floor screen searches against `clientes`, not each tramite table: the
   * operator's real question is "who is this person and what do they have
   * open", which is exactly what the relational model made possible.
   */
  buscarClientes(termino: string, limit = 8): Observable<Paginado<Cliente>> {
    const params = new HttpParams().set('buscar', termino).set('limit', String(limit));
    return this.http.get<Paginado<Cliente>>(`${this.baseUrl}/clientes/`, {
      ...this.opciones,
      params,
    });
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
