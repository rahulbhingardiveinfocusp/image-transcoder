import { ChangeDetectorRef, Component } from '@angular/core';
import { AuthService } from '../../service/auth-service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { Router } from '@angular/router';
export interface AdminStats {
  total_users: number;
  total_files: number;
}

export interface UserSummary {
  user_id: string;
  email: string;
  files_count: number;
  last_upload: string;
}

export interface UserFile {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  url: string;
}

@Component({
  selector: 'app-admin-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule],
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.css']
})

export class AdminDashboardComponent {
  stats: AdminStats = {
    total_users: 0,
    total_files: 0
  };

  users: UserSummary[] = [];

  selectedUser?: UserSummary;

  userFiles: UserFile[] = [];

  loadingUsers = false;
  loadingFiles = false;

  searchTerm = '';

  constructor(
  private http: HttpClient,
  private router: Router,
  private auth: AuthService,
  private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadDashboard();
  }

  loadDashboard() {
    this.loadStats();
    this.loadUsers();
  }

  loadStats() {
    this.http
      .get<AdminStats>('/api/v1/admin/stats')
      .subscribe(res => {
        this.stats = res;
        this.cdr.markForCheck();
      });
  }

  loadUsers() {
    this.loadingUsers = true;

    this.http
      .get<UserSummary[]>('/api/v1/admin/users')
      .subscribe({
        next: users => {
          this.users = users;
          this.loadingUsers = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingUsers = false;
          this.cdr.markForCheck();
        }
      });
  }

  viewUser(user: UserSummary) {
    this.selectedUser = user;

    this.loadingFiles = true;

    this.http
      .get<UserFile[]>(
        `/api/v1/admin/users/${user.user_id}/files`
      )
      .subscribe({
        next: files => {
          this.userFiles = files;
          this.loadingFiles = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loadingFiles = false;
          this.cdr.markForCheck();
        }
      });
  }
  viewFiles(user: UserSummary) {
  this.router.navigate([
    '/admin/users',
    user.user_id,
    'files'
  ]);
}
  get filteredUsers() {
    if (!this.searchTerm) return this.users;

    const term = this.searchTerm.toLowerCase();

    return this.users.filter(
      x =>
        x.email.toLowerCase().includes(term)
    );
  }

  logout() {
    this.auth.logout();
  }
}