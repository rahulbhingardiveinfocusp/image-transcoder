import { Injectable } from '@angular/core';
import {
  HttpInterceptor,
  HttpRequest,
  HttpHandler,
  HttpEvent,
} from '@angular/common/http';
import { Observable, from } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { AuthService } from './app/service/auth-service';
import { environment } from './environments/environment';



@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private auth: AuthService) {}

  intercept(
    req: HttpRequest<any>,
    next: HttpHandler
  ): Observable<HttpEvent<any>> {
    // Only attach JWT to your backend API
    if (!req.url.startsWith(environment.apiUrl)) {
      return next.handle(req);
    }

    return from(this.auth.getJwt()).pipe(
      switchMap((token) => {
        if (!token) {
          return next.handle(req);
        }

        const cloned = req.clone({
          setHeaders: {
            Authorization: `Bearer ${token}`,
          },
        });

        return next.handle(cloned);
      })
    );
  }
}