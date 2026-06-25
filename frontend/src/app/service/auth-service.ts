import { Injectable } from '@angular/core';
import {
  signIn,
  signUp,
  signOut,
  confirmSignUp,
  getCurrentUser,
  fetchAuthSession,
} from 'aws-amplify/auth';

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  async signUp(email: string, password: string) {
    return signUp({
      username: email,
      password,
      options: {
        userAttributes: {
          email,
        },
      },
    });
  }

  async confirm(email: string, code: string) {
    return confirmSignUp({
      username: email,
      confirmationCode: code,
    });
  }

  async login(email: string, password: string) {
    return signIn({
      username: email,
      password,
    });
  }

  async logout() {
    await signOut();
    window.location.reload();
    return true;
  }

  async currentUser() {
    return getCurrentUser();
  }

  async getGroups(): Promise<string[]> {
    const session = await fetchAuthSession();

    const groupsClaim = session.tokens?.idToken?.payload?.['cognito:groups'];

    if (Array.isArray(groupsClaim)) {
      return groupsClaim.filter((item): item is string => typeof item === 'string');
    }

    if (typeof groupsClaim === 'string') {
      return [groupsClaim];
    }

    return [];
  }

  async isAdmin(): Promise<boolean> {
    const groups = await this.getGroups();

    return groups.includes('Admin');
  }

  async getJwt(): Promise<string | null> {
    try {
      const session = await fetchAuthSession();

      const token = session.tokens?.accessToken?.toString();

      console.log('AuthService token:', token);

      return token ?? null;
    } catch (e) {
      console.error('getJwt failed:', e);
      return null;
    }
  }
}
