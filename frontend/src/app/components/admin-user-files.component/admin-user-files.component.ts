import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  OnInit
} from '@angular/core';

import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

interface UserFile {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  url: string;
}

@Component({
  selector: 'app-admin-user-files',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin-user-files.component.html',
  styleUrl: './admin-user-files.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AdminUserFilesComponent implements OnInit {
  private apiBaseUrl = environment.apiUrl;
  userId = '';

  files: UserFile[] = [];

  loading = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.userId =
      this.route.snapshot.paramMap.get('userId') || '';

    this.loadFiles();
  }

  loadFiles() {
    this.loading = true;

    this.http
      .get<UserFile[]>(
        `${this.apiBaseUrl}/api/v1/admin/users/${this.userId}/files`
      )
      .subscribe({
        next: files => {
          this.files = files;
          this.loading = false;
          this.cdr.markForCheck();
        },
        error: () => {
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  back() {
    this.router.navigate(['/admin']);
  }

  trackById(index: number, item: UserFile) {
    return item.id;
  }

  getStatusClass(status: string) {
    switch ((status || '').toLowerCase()) {
      case 'completed':
        return 'badge-success';
      case 'processing':
        return 'badge-processing';
      case 'failed':
        return 'badge-failed';
      default:
        return 'badge-pending';
    }
  }
}