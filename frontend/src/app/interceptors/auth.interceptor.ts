import { inject } from '@angular/core';
import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const authService = inject(AuthService);
  const router = inject(Router);
  const token = authService.getToken();

  let clonedRequest = req;
  
  // Clonar la solicitud y adjuntar el token si está disponible
  if (token) {
    clonedRequest = req.clone({
      headers: req.headers.set('Authorization', `Bearer ${token}`)
    });
  }

  // Interceptar errores de respuesta (por ejemplo, 401 Unauthorized)
  return next(clonedRequest).pipe(
    catchError((error: any) => {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        authService.logout();
        router.navigate(['/login']);
      }
      return throwError(() => error);
    })
  );
};
