import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  ChangeDetectionStrategy,
  ChangeDetectorRef
} from '@angular/core';

import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { environment } from '../environments/environment';
import { interval, Subject, takeUntil } from 'rxjs';

type PreSignedResponse = {
  image_id: string;
  upload_url: string;
};

type ImageItem = {
  id: string;
  filename: string;
  status: string;
  s3_key: string;
  created_at: string;
};

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css',
  imports: [CommonModule, FormsModule, HttpClientModule],
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class App implements OnInit, OnDestroy {
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
    private cdr: ChangeDetectorRef
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

    this.http.get<ImageItem[]>(`${this.apiBaseUrl}/api/v1/get-all-images`)
      .subscribe({
        next: (data) => {
          this.images = data;

          this.loading = false;

          // 🔥 critical for OnPush reliability
          this.cdr.markForCheck();
        },
        error: () => {
          this.loading = false;
          this.cdr.markForCheck();
        }
      });
  }

  // ✅ computed UI data (no extra state)
  get filteredImages(): ImageItem[] {
    let data = this.images;

    if (this.searchTerm) {
      const term = this.searchTerm.toLowerCase();
      data = data.filter(x =>
        x.filename.toLowerCase().includes(term)
      );
    }

    if (this.statusFilter !== 'ALL') {
      data = data.filter(x => x.status === this.statusFilter);
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
      this.sortDirection =
        this.sortDirection === 'asc' ? 'desc' : 'asc';
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

    this.http.post<PreSignedResponse>(
      `${this.apiBaseUrl}/api/v1/request-upload`,
      {
        filename: file.name,
        content_type: file.type,
      }
    ).subscribe({
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
      }
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
}