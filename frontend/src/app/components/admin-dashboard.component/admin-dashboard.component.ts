import { Component } from '@angular/core';
import { AuthService } from '../../service/auth-service';
@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  template: `
    <h1>Admin Dashboard</h1>

    <p>Only Admin users can see this page.</p>
  `
})
export class AdminDashboardComponent {
    constructor(
    private auth: AuthService
  ) {

  }
  logout(){
    this.auth.logout()
  }
}