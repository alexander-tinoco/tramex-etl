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
  templateUrl: './login.component.html',
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
