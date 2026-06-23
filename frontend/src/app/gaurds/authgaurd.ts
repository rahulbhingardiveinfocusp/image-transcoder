import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { getCurrentUser } from 'aws-amplify/auth';

export const authGuard: CanActivateFn = async () => {

  const router = inject(Router);

  try {

    await getCurrentUser();

    return true;

  } catch {

    router.navigate(['/']);

    return false;
  }
};