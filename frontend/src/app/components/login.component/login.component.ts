import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../service/auth-service';



@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule
  ],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css']
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
    private router: Router
  ) {}

  async login() {

    this.error = '';
    this.success = '';

    try {

      this.loading = true;

      const result = await this.auth.login(
        this.email,
        this.password
      );

      console.log(result);

      const isAdmin =
        await this.auth.isAdmin();

      if (isAdmin) {
        this.router.navigate(['/admin']);
      } else {
        this.router.navigate(['/user']);
      }

    } catch (err: any) {

      this.error =
        err?.message ||
        'Login failed';

    } finally {

      this.loading = false;
    }
  }

  async signup() {

    this.error = '';
    this.success = '';

    try {

      this.loading = true;

      const result =
        await this.auth.signUp(
          this.email,
          this.password
        );

      console.log(result);

      this.showConfirmation = true;

      this.success =
        'Verification code sent to email';

    } catch (err: any) {

      this.error =
        err?.message ||
        'Signup failed';

    } finally {

      this.loading = false;
    }
  }

  async confirmSignup() {

    this.error = '';

    try {

      this.loading = true;

      await this.auth.confirm(
        this.email,
        this.verificationCode
      );

      this.success =
        'Account verified successfully';

      this.showConfirmation = false;

    } catch (err: any) {

      this.error =
        err?.message ||
        'Verification failed';

    } finally {

      this.loading = false;
    }
  }
}