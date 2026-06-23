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
    this.loading = true;

    try {
      await this.auth.login(this.email, this.password);

      const isAdmin = await this.auth.isAdmin();
      this.router.navigate([isAdmin ? '/admin' : '/user']);
    } catch (err: any) {
      if (err?.name === 'UserNotConfirmedException') {
        this.showConfirmation = true;
        this.success = 'Please verify your account first';
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
    this.loading = true;

    // 🔥 ALWAYS switch UI first
    this.showConfirmation = true;

    try {
      await this.auth.signUp(this.email, this.password);
      this.success = 'Verification code sent to email';
    } catch (err: any) {
      this.showConfirmation = false;
      this.error = err?.message || 'Signup failed';
    } finally {
      this.loading = false;
    }
  }

  async confirmSignup() {
    this.error = '';
    this.loading = true;

    try {
      await this.auth.confirm(this.email, this.verificationCode);

      // auto login after confirmation
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
    this.error = '';
    this.success = '';
    this.loading = true;

    try {
      await resendSignUpCode({ username: this.email });
      this.success = 'A new code has been sent to your email.';
    } catch (err: any) {
      this.error = err?.message || 'Failed to resend code';
    } finally {
      this.loading = false;
    }
  }
}
