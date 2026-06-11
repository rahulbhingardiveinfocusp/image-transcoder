import { Component } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  selectedFile: File | null = null;
  private apiBaseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  onFileSelected(event: any) {
    if (event.target.files?.length > 0) {
      this.selectedFile = event.target.files[0];
    }
  }

  onUpload() {
    if (!this.selectedFile) {
      alert('Please select a file first!');
      return;
    }

    const file = this.selectedFile;

    // 1. Get presigned URL
    this.http
      .post<any>(`${this.apiBaseUrl}/images/request-upload`, {
        filename: file.name,
        content_type: file.type,
      })
      .subscribe({
        next: (res) => {
          const uploadUrl = res.upload_url;

          // IMPORTANT: MUST use headers in PUT request
          const headers = new HttpHeaders({
            'Content-Type': file.type,
          });
          // 2. Upload directly to S3
          this.http.put(uploadUrl, file, { headers }).subscribe({
            next: () => {
              alert('Upload successful!');
              this.selectedFile = null;
            },
            error: (err) => {
              console.error('S3 Upload failed:', err);
            },
          });
        },
        error: (err) => {
          console.error('Backend failed:', err);
          alert('Failed to get upload URL from server.');
        },
      });
  }
}
