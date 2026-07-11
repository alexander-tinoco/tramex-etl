import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div id="login-screen" class="screen active">
      <div class="login-wrapper">
        <div class="login-glow"></div>
        <div class="login-card">
          <div class="login-header">
            <div class="logo-icon">
              <i class="fa-solid fa-passport"></i>
            </div>
            <h1>Tramex System</h1>
            <p>Gestión Inteligente de Trámites</p>
          </div>
          <form (submit)="onSubmit($event)">
            <div class="form-group">
              <label for="username"><i class="fa-solid fa-user"></i> Usuario</label>
              <input type="text" id="username" name="username" [(ngModel)]="username" required placeholder="Ingresa tu usuario">
            </div>
            <div class="form-group">
              <label for="password"><i class="fa-solid fa-lock"></i> Contraseña</label>
              <div class="password-input-wrapper">
                <input [type]="showPassword ? 'text' : 'password'" id="password" name="password" [(ngModel)]="password" required placeholder="Ingresa tu contraseña">
                <button type="button" class="btn-toggle-pwd" (click)="togglePassword()">
                  <i class="fa-solid" [ngClass]="showPassword ? 'fa-eye-slash' : 'fa-eye'"></i>
                </button>
              </div>
            </div>
            <div *ngIf="errorMessage" class="alert error">
              <i class="fa-solid fa-circle-exclamation"></i> <span>{{errorMessage}}</span>
            </div>
            <button type="submit" class="btn-primary btn-block" [disabled]="loading">
              <span *ngIf="!loading">Ingresar</span>
              <span *ngIf="loading"><i class="fa-solid fa-spinner fa-spin"></i> Cargando...</span>
              <i *ngIf="!loading" class="fa-solid fa-arrow-right-to-bracket"></i>
            </button>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: []
})
export class LoginComponent {
  username = '';
  password = '';
  showPassword = false;
  errorMessage = '';
  loading = false;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private router: Router
  ) {}

  togglePassword() {
    this.showPassword = !this.showPassword;
  }

  onSubmit(event: Event) {
    event.preventDefault();
    if (!this.username || !this.password) return;

    this.loading = true;
    this.errorMessage = '';

    const bodyParams = new URLSearchParams();
    bodyParams.append('username', this.username);
    bodyParams.append('password', this.password);

    this.api.login(bodyParams).subscribe({
      next: (data) => {
        this.auth.setToken(data.access_token);
        this.loading = false;
        this.router.navigate(['/dashboard']);
      },
      error: (err) => {
        this.loading = false;
        if (err.status === 401) {
          this.errorMessage = 'Usuario o contraseña incorrectos.';
        } else {
          this.errorMessage = 'Error al conectar con el servidor.';
        }
      }
    });
  }
}
