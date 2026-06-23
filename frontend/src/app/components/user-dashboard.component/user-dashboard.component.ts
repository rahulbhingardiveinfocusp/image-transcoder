import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  ChangeDetectionStrategy,
  ChangeDetectorRef,
} from '@angular/core';

import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { interval, Subject, takeUntil } from 'rxjs';
import { environment } from '../../../environments/environment';

type PreSignedResponse = {
  image_id: string;
  upload_url: string;
};

type ImageItem = {
  id: string;
  filename: string;
  status: string;
  s3_key: string;
  processed_s3_key:string;
  created_at: string;
  url: string;
};

@Component({
  selector: 'app-user-dashboard.component',
  imports: [CommonModule, FormsModule, HttpClientModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './user-dashboard.component.html',
  styleUrl: './user-dashboard.component.css',
})
export class UserDashboardComponent {
  @ViewChild('fileInput') fileInput!: ElementRef;

  selectedFile: File | null = null;

  images: ImageItem[] = [];

  searchTerm = '';
  statusFilter = 'ALL';

  loading = false;
  uploading = false;

  sortColumn: keyof ImageItem = 'created_at';
  sortDirection: 'asc' | 'desc' = 'desc';

  private apiBaseUrl = environment.apiUrl;
  private destroy$ = new Subject<void>();

  constructor(
    private http: HttpClient,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadImages();

    interval(30000)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => this.loadImages());
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files?.[0] ?? null;
    this.cdr.markForCheck();
  }

  // ✅ FIXED: ensures UI always updates (including first call)
  loadImages() {
    this.loading = true;
    this.cdr.markForCheck();

    this.http.get<ImageItem[]>(`${this.apiBaseUrl}/api/v1/get-all-images`).subscribe({
      next: (data) => {
        this.images = data;

        this.loading = false;

        // 🔥 critical for OnPush reliability
        this.cdr.markForCheck();
      },
      error: () => {
        this.loading = false;
        this.cdr.markForCheck();
      },
    });
  }

  // ✅ computed UI data (no extra state)
  get filteredImages(): ImageItem[] {
    let data = this.images;

    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      data = data.filter((x) => x.filename.toLowerCase().includes(term));
    }

    if (this.statusFilter !== 'ALL') {
      data = data.filter((x) => x.status === this.statusFilter);
    }

    return this.sortData(data);
  }

  private sortData(data: ImageItem[]) {
    return [...data].sort((a, b) => {
      const aVal = a[this.sortColumn];
      const bVal = b[this.sortColumn];

      if (aVal == null || bVal == null) return 0;

      if (this.sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      }

      return aVal < bVal ? 1 : -1;
    });
  }

  sort(column: keyof ImageItem) {
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column;
      this.sortDirection = 'asc';
    }

    this.cdr.markForCheck();
  }

  async onUpload() {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.cdr.markForCheck();

    const file = this.selectedFile;

    this.http
      .post<PreSignedResponse>(`${this.apiBaseUrl}/api/v1/request-upload`, {
        filename: file.name,
        content_type: file.type,
      })
      .subscribe({
        next: (res) => {
          fetch(res.upload_url, {
            method: 'PUT',
            headers: { 'Content-Type': file.type },
            body: file,
          })
            .then((response) => {
              if (!response.ok) throw new Error();

              this.selectedFile = null;
              if (this.fileInput) {
                this.fileInput.nativeElement.value = '';
              }

              this.uploading = false;

              // 🔥 refresh UI
              this.loadImages();
            })
            .catch(() => {
              this.uploading = false;
              this.cdr.markForCheck();
              alert('Upload failed');
            });
        },
        error: () => {
          this.uploading = false;
          this.cdr.markForCheck();
        },
      });
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

  trackById(index: number, item: ImageItem) {
    return item.id;
  }

  async shareOriginal(img: any): Promise<void> {debugger
    await this.shareUrl(img.filename, img.s3_key);
  }

  async shareProcessed(img: any): Promise<void> {debugger
    await this.shareUrl(`${img.filename} (Processed)`, img.url);
  }
  private async shareUrl(title: string, url: string): Promise<void> {
    if (!url) {
      alert('URL not available');
      return;
    }
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
      } else {
        await this.copyToClipboard(url);
      }
    } catch (err) {
      console.error(err);
    }
  }

  private copyToClipboard(url: string): void {
    // fallback that works even when document is not focused
    const el = document.createElement('textarea');
    el.value = url;
    el.style.position = 'fixed';
    el.style.opacity = '0';
    document.body.appendChild(el);
    el.focus();
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    alert('Link copied to clipboard');
  }
}
