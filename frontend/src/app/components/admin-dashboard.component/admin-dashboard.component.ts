import { Component } from '@angular/core';

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  template: `
    <h1>Admin Dashboard</h1>

    <p>Only Admin users can see this page.</p>
  `
})
export class AdminDashboardComponent {}