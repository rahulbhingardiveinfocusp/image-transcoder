import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { CommonModule,DatePipe } from '@angular/common';
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
  imports: [
    CommonModule,
    FormsModule,
    HttpClientModule
  ],
})
export class App implements OnInit, OnDestroy {
  @ViewChild('fileInput') fileInput!: ElementRef;

  selectedFile: File | null = null;
  images: ImageItem[] = [];
  filteredImages: ImageItem[] = [];

  searchTerm = '';
  statusFilter = 'ALL';

  loading = false;
  uploading = false;

  sortColumn = 'created_at';
  sortDirection: 'asc' | 'desc' = 'desc';

  private apiBaseUrl = environment.apiUrl;
  private destroy$ = new Subject<void>();

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.loadImages();

    interval(30000)
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => {
        this.loadImages();
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files?.[0] ?? null;
  }

  loadImages() {
    this.loading = true;

    this.http.get<ImageItem[]>(`${this.apiBaseUrl}/api/vi/get-all-images`).subscribe({
      next: (data) => {
        this.images = data;
        this.applyFilters();
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }

  applyFilters() {
    let data = [...this.images];

    if (this.searchTerm) {
      data = data.filter((x) => x.filename.toLowerCase().includes(this.searchTerm.toLowerCase()));
    }

    if (this.statusFilter !== 'ALL') {
      data = data.filter((x) => x.status === this.statusFilter);
    }

    data.sort((a: any, b: any) => {
      const aVal = a[this.sortColumn];
      const bVal = b[this.sortColumn];

      if (this.sortDirection === 'asc') {
        return aVal > bVal ? 1 : -1;
      }

      return aVal < bVal ? 1 : -1;
    });

    this.filteredImages = data;
  }

  sort(column: string) {
    if (this.sortColumn === column) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column;
      this.sortDirection = 'asc';
    }

    this.applyFilters();
  }

  async onUpload() {
    if (!this.selectedFile) {
      return;
    }

    this.uploading = true;

    const file = this.selectedFile;

    this.http
      .post<PreSignedResponse>(`${this.apiBaseUrl}/api/vi/request-upload`, {
        filename: file.name,
        content_type: file.type,
      })
      .subscribe({
        next: (res) => {
          fetch(res.upload_url, {
            method: 'PUT',
            headers: {
              'Content-Type': file.type,
            },
            body: file,
          })
            .then((response) => {
              if (!response.ok) {
                throw new Error();
              }

              this.selectedFile = null;

              if (this.fileInput) {
                this.fileInput.nativeElement.value = '';
              }

              this.loadImages();
              this.uploading = false;
            })
            .catch(() => {
              this.uploading = false;
              alert('Upload failed');
            });
        },
        error: () => {
          this.uploading = false;
        },
      });
  }

  getStatusClass(status: string) {
    switch (status?.toLowerCase()) {
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
