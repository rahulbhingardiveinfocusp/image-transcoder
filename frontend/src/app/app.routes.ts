import { Routes } from '@angular/router';
import { authGuard } from './gaurds/authgaurd';


export const routes: Routes = [

  {
    path: '',
    loadComponent: () =>
      import('./components/login.component/login.component')
        .then(m => m.LoginComponent)
  },

  {
    path: 'admin',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/admin-dashboard.component/admin-dashboard.component')
        .then(m => m.AdminDashboardComponent)
  },

  {
    path: 'user',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./components/user-dashboard.component/user-dashboard.component')
        .then(m => m.UserDashboardComponent)
  },

  {
    path: '**',
    redirectTo: ''
  }
];