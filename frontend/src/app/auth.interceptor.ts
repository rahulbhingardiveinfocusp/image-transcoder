import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, of } from 'rxjs';
import { switchMap, catchError } from 'rxjs/operators';
import { AuthService } from './service/auth-service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);

  const isApi = req.url.includes('/api/');

  if (!isApi) {
    return next(req);
  }

  return from(auth.getJwt()).pipe(
    switchMap((token) => {
      console.log('JWT token in interceptor:', token);

      if (!token) {
        return next(req);
      }

      return next(
        req.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        })
      );
    }),
    catchError((err) => {
      console.error('Interceptor auth error:', err);
      return next(req);
    })
  );
};