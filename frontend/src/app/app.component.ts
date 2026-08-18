import { Component, OnInit, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<router-outlet />`,
})
export class AppComponent implements OnInit {
  private readonly auth = inject(AuthService);

  ngOnInit(): void {
    // La cookie de sesion es `httpOnly` y por tanto invisible para el
    // navegador: la unica forma de saber si hay sesion tras recargar la pagina
    // es preguntarle a la API. Un 401 aqui es una respuesta normal (no hay
    // sesion), no un error, y el interceptor lo trata como tal.
    this.auth.cargarSesion().subscribe({ error: () => undefined });
  }
}
