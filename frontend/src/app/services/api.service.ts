import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8000';

  constructor(private http: HttpClient, private auth: AuthService) {}

  private getHeaders(): HttpHeaders {
    const token = this.auth.getToken();
    return new HttpHeaders({
      'Authorization': `Bearer ${token || ''}`
    });
  }

  login(bodyParams: URLSearchParams): Observable<any> {
    return this.http.post(`${this.baseUrl}/api/auth/token`, bodyParams.toString(), {
      headers: new HttpHeaders({ 'Content-Type': 'application/x-www-form-urlencoded' })
    });
  }

  checkHealth(): Observable<any> {
    return this.http.get(`${this.baseUrl}/health`, { headers: this.getHeaders() });
  }

  getList(endpoint: string, skip: number, limit: number, search?: string): Observable<any> {
    let url = `${this.baseUrl}${endpoint}?skip=${skip}&limit=${limit}`;
    if (search) {
      url += `&buscar=${encodeURIComponent(search)}`;
    }
    return this.http.get(url, { headers: this.getHeaders() });
  }

  createRecord(endpoint: string, body: any): Observable<any> {
    return this.http.post(`${this.baseUrl}${endpoint}`, body, { headers: this.getHeaders() });
  }

  updateRecord(endpoint: string, id: number, body: any): Observable<any> {
    return this.http.patch(`${this.baseUrl}${endpoint}${id}`, body, { headers: this.getHeaders() });
  }

  deleteRecord(endpoint: string, id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}${endpoint}${id}`, { headers: this.getHeaders() });
  }

  getPassword(endpoint: string, id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}${endpoint}${id}/password`, { headers: this.getHeaders() });
  }
}
