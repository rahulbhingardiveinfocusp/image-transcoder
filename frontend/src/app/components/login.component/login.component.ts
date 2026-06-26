import { ChangeDetectorRef, Component, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../service/auth-service';
import { resendSignUpCode } from 'aws-amplify/auth';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
})
export class LoginComponent {
  email = '';
  password = '';
  verificationCode = '';

  showConfirmation = false;
  loading = false;

  error = '';
  success = '';

  constructor(
    private auth: AuthService,
    private router: Router,
    private cdr: ChangeDetectorRef
  ) {}

login() {
  this.error = '';
  this.success = '';
  this.loading = true;

  this.auth.login(this.email, this.password)
    .then(() => this.auth.isAdmin())
    .then((isAdmin) => {
      this.router.navigate([isAdmin ? '/admin' : '/user']);
    })
    .catch((err) => {
      console.log('ERROR:', err);

      this.error = err?.message || 'Login failed';
       this.cdr.detectChanges(); 
    })
    .finally(() => {
      this.loading = false;
    });
}

  isAdmin() {
    return this.auth
      .isAdmin()
      .then((isAdmin) => {
        this.router.navigate([isAdmin ? '/admin' : '/user']);
      })
      .catch((err: any) => {
        this.error = err?.message;
         this.cdr.detectChanges(); 
      })
      .finally(() => (this.loading = false));
  }
  signup() {
    this.error = '';
    this.success = '';
    this.loading = true;
    this.showConfirmation = true;

    this.auth
      .signUp(this.email, this.password)
      .then(() => {
        this.success = 'Verification code sent to email';
      })
      .catch((err: any) => {
        this.showConfirmation = false;
        this.error = err?.message || 'Signup failed';
      })
      .finally(() => (this.loading = false));
  }

  confirmSignup() {
    this.error = '';
    this.loading = true;

    this.auth
      .confirm(this.email, this.verificationCode)
      .then(() => this.auth.login(this.email, this.password))
      .then(() => this.auth.isAdmin())
      .then((isAdmin) => {
        this.router.navigate([isAdmin ? '/admin' : '/user']);
      })
      .catch((err: any) => {
        this.error = err?.message || 'Verification failed';
      })
      .finally(() => (this.loading = false));
  }

  resendCode() {
    this.error = '';
    this.success = '';
    this.loading = true;

    resendSignUpCode({ username: this.email })
      .then(() => {
        this.success = 'A new code has been sent to your email.';
      })
      .catch((err: any) => {
        this.error = err?.message || 'Failed to resend code';
      })
      .finally(() => (this.loading = false));
  }
}
