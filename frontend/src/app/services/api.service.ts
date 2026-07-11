import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private http = inject(HttpClient);

  private baseUrl = environment.apiUrl;

  login(bodyParams: URLSearchParams): Observable<any> {
    return this.http.post(`${this.baseUrl}/api/auth/token`, bodyParams.toString(), {
      headers: new HttpHeaders({ 'Content-Type': 'application/x-www-form-urlencoded' })
    });
  }

  checkHealth(): Observable<any> {
    return this.http.get(`${this.baseUrl}/health`);
  }

  getList(endpoint: string, skip: number, limit: number, search?: string): Observable<any> {
    let url = `${this.baseUrl}${endpoint}?skip=${skip}&limit=${limit}`;
    if (search) {
      url += `&buscar=${encodeURIComponent(search)}`;
    }
    return this.http.get(url);
  }

  createRecord(endpoint: string, body: any): Observable<any> {
    return this.http.post(`${this.baseUrl}${endpoint}`, body);
  }

  updateRecord(endpoint: string, id: number, body: any): Observable<any> {
    return this.http.patch(`${this.baseUrl}${endpoint}${id}`, body);
  }

  deleteRecord(endpoint: string, id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}${endpoint}${id}`);
  }

  getPassword(endpoint: string, id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}${endpoint}${id}/password`);
  }
}
