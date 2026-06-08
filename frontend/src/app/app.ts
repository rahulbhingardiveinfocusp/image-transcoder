import { Component } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
// 👇 FIXED: Always import the base environment file. 
// Angular's compiler will automatically swap this out for environment.prod during CI/CD!
import { environment } from '../environments/environment';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  selectedFile: File | null = null;
  // Use a fallback to prevent runtime crashes if the variable is missing
  private apiBaseUrl = environment.apiUrl || 'http://localhost:8000';

  constructor(private http: HttpClient) { }

  onFileSelected(event: any) {
    if (event.target.files && event.target.files.length > 0) {
      this.selectedFile = event.target.files[0];
    }
  }

  onUpload() {
    if (!this.selectedFile) {
      alert('Please select a file first!');
      return;
    }

    // 1. Ask FastAPI for the pre-signed URL
    this.http.post(`${this.apiBaseUrl}/images/request-upload`, {
      filename: this.selectedFile.name
    }).subscribe({
      next: (res: any) => {
        const uploadUrl = res.upload_url;
        
        // 2. Upload the file directly to S3 using the pre-signed URL
        const headers = new HttpHeaders({ 'Content-Type': this.selectedFile!.type });

        this.http.put(uploadUrl, this.selectedFile, { headers }).subscribe({
          next: () => {
            alert('Upload successful!');
            this.selectedFile = null; // Clear the selection on success
          },
          error: (err) => {
            console.error('S3 Direct Upload failed:', err);
            alert('Failed to upload file to storage.');
          }
        });
      },
      error: (err) => {
        console.error('FastAPI Pre-signed URL generation failed:', err);
        alert('Failed to connect to the backend server.');
      }
    });
  }
}