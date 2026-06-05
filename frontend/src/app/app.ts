import { Component } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  selectedFile: File | null = null;
  private apiBaseUrl = 'http://localhost:8000'; // Your FastAPI URL

  constructor(private http: HttpClient) { }

  onFileSelected(event: any) {
    this.selectedFile = event.target.files[0];
  }

  onUpload() {
    if (!this.selectedFile) return;

    // 1. Ask FastAPI for the pre-signed URL
    this.http.post(`${this.apiBaseUrl}/images/request-upload`, {
      filename: this.selectedFile.name
    }).subscribe((res: any) => {
      const uploadUrl = res.upload_url;

      // 2. Upload the file directly to S3
      const headers = new HttpHeaders({ 'Content-Type': this.selectedFile!.type });

      this.http.put(uploadUrl, this.selectedFile, { headers }).subscribe({
        next: () => alert('Upload successful!'),
        error: (err) => console.error('Upload failed', err)
      });
    });
  }
}
