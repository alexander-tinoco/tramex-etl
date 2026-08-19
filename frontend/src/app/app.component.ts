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
    // The session cookie is `httpOnly` and therefore invisible to the
    // browser: the only way to know whether there's a session after
    // reloading the page is to ask the API. A 401 here is a normal response
    // (no session), not an error, and the interceptor treats it as such.
    this.auth.cargarSesion().subscribe({ error: () => undefined });
  }
}
