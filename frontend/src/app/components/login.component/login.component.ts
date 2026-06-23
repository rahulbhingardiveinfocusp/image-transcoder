import { Component } from '@angular/core';
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
  ) {}

  async login() {
    this.error = '';
    this.success = '';

    try {
      this.loading = true;

      await this.auth.login(this.email, this.password);

      const isAdmin = await this.auth.isAdmin();
      this.router.navigate([isAdmin ? '/admin' : '/user']);
    } catch (err: any) {
      if (err.name === 'UserNotConfirmedException') {
        // Resend code and show confirmation input
        await resendSignUpCode({ username: this.email });
        this.showConfirmation = true;
        this.success = 'Please verify your account. A new code has been sent to your email.';
      } else {
        this.error = err?.message || 'Login failed';
      }
    } finally {
      this.loading = false;
    }
  }

  async signup() {
    this.error = '';
    this.success = '';

    try {
      this.loading = true;

      const result = await this.auth.signUp(this.email, this.password);

      console.log(result);

      this.showConfirmation = true;

      this.success = 'Verification code sent to email';
    } catch (err: any) {
      this.error = err?.message || 'Signup failed';
    } finally {
      this.loading = false;
    }
  }

  async confirmSignup() {
    this.error = '';

    try {
      this.loading = true;

      await this.auth.confirm(this.email, this.verificationCode);

      // Log them straight in instead of making them re-enter credentials
      await this.auth.login(this.email, this.password);

      const isAdmin = await this.auth.isAdmin();
      this.router.navigate([isAdmin ? '/admin' : '/user']);
    } catch (err: any) {
      this.error = err?.message || 'Verification failed';
    } finally {
      this.loading = false;
    }
  }
  async resendCode() {
    try {
      this.loading = true;
      await resendSignUpCode({ username: this.email });
      this.success = 'A new code has been sent to your email.';
      this.error = '';
    } catch (err: any) {
      this.error = err?.message || 'Failed to resend code';
    } finally {
      this.loading = false;
    }
  }
}
