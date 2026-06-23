import { Component } from '@angular/core';
import { AuthService } from '../../service/auth-service';
@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.css']
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