import { ChangeDetectorRef, Component, OnInit } from '@angular/core';
import { AuthService } from '../../service/auth-service';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';

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
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-dashboard.component.html',
  styleUrls: ['./admin-dashboard.component.css']
})
export class AdminDashboardComponent implements OnInit {

  stats: AdminStats = { total_users: 0, total_files: 0 };
  users: UserSummary[] = [];
  selectedUser?: UserSummary;
  userFiles: UserFile[] = [];
  loadingUsers = false;
  loadingFiles = false;
  searchTerm = '';
  modalOpen = false;
  private apiBaseUrl = environment.apiUrl;
  constructor(
    private http: HttpClient,
    private router: Router,
    private auth: AuthService,
    private cdr: ChangeDetectorRef,
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
      .get<AdminStats>(`${this.apiBaseUrl}/api/v1/admin/stats`)
      .subscribe(res => {
        this.stats = res;
        this.cdr.markForCheck();
      });
  }

  loadUsers() {
    this.loadingUsers = true;
    this.http
      .get<UserSummary[]>(`${this.apiBaseUrl}/api/v1/admin/users`)
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

  openModal(user: UserSummary) {
    this.selectedUser = user;
    this.userFiles = [];
    this.modalOpen = true;
    this.loadingFiles = true;

    this.http
      .get<UserFile[]>(`${this.apiBaseUrl}/api/v1/admin/users/${user.user_id}/files`)
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

  closeModal() {
    this.modalOpen = false;
    this.selectedUser = undefined;
    this.userFiles = [];
  }

  getStatusClass(status: string): string {
    const map: Record<string, string> = {
      completed:  'badge-success',
      processing: 'badge-processing',
      failed:     'badge-failed',
      pending:    'badge-pending',
    };
    return map[status] ?? 'badge-pending';
  }

  get filteredUsers() {
    if (!this.searchTerm) return this.users;
    const term = this.searchTerm.toLowerCase();
    return this.users.filter(u => u.email.toLowerCase().includes(term));
  }

  logout() {
    this.auth.logout();
  }
}