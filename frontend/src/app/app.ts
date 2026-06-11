import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css'
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

    // 1. Get presigned URL from backend
    this.http.post<any>(
      `${this.apiBaseUrl}/images/request-upload`,
      { filename: file.name }
    ).subscribe({
      next: async (res) => {
        const uploadUrl = res.upload_url;

        try {
          // 2. Upload directly to S3 (NO HEADERS)
          await fetch(uploadUrl, {
            method: 'PUT',
            body: file
          });

          alert('Upload successful!');
          this.selectedFile = null;

        } catch (err) {
          console.error('S3 Upload failed:', err);
        }
      },

      error: (err) => {
        console.error('Backend failed:', err);
        alert('Failed to get upload URL from server.');
      }
    });
  }
}