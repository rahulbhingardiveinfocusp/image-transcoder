import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { AuthService } from './service/auth-service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  console.log('🧠 INTERCEPTOR ENTERED:', req.url);

  return from(auth.getJwt()).pipe(
    switchMap((token) => {
      console.log('🔐 TOKEN RECEIVED:', token);

      const cloned = token
        ? req.clone({
            setHeaders: {
              Authorization: `Bearer ${token}`,
            },
          })
        : req;

      console.log('🚀 FINAL HEADERS:', cloned.headers.keys());

      return next(cloned);
    }),
    catchError((err) => {
      console.error('💥 INTERCEPTOR ERROR:', err);
      return next(req);
    })
  );
};