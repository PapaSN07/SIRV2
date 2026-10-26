import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

function isForcePasswordChange(err: unknown): boolean {
  const detail = (err as { error?: { detail?: { error?: unknown } } })?.error?.detail?.error;
  return (
    typeof detail === 'object' &&
    detail !== null &&
    'code' in detail &&
    (detail as { code?: string }).code === 'FORCE_PASSWORD_CHANGE'
  );
}

@Component({
  selector: 'sir-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './login.component.html',
  styleUrl: './login.component.scss',
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  /** Page demandée avant la connexion (lien partagé, session expirée) ; adresses internes uniquement. */
  private returnUrl(): string {
    const url = this.route.snapshot.queryParamMap.get('returnUrl') ?? '/';
    return url.startsWith('/') && !url.startsWith('//') ? url : '/';
  }

  loading = false;
  errorMessage = '';
  hidePassword = true;

  readonly form = this.fb.nonNullable.group({
    login: ['', Validators.required],
    password: ['', Validators.required],
  });

  togglePasswordVisibility(): void {
    this.hidePassword = !this.hidePassword;
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    this.loading = true;
    this.errorMessage = '';

    this.auth.signIn(this.form.getRawValue()).subscribe({
      next: () => {
        this.loading = false;
        void this.router.navigateByUrl(this.returnUrl());
      },
      error: (err: { error?: { detail?: { error?: string | { code?: string; message?: string } } } }) => {
        this.loading = false;
        if (isForcePasswordChange(err)) {
          void this.router.navigate(['/changer-mot-de-passe'], {
            queryParams: { login: this.form.getRawValue().login },
          });
          return;
        }
        const detail = err.error?.detail?.error;
        this.errorMessage =
          typeof detail === 'string'
            ? detail
            : typeof detail === 'object' && detail?.message
              ? detail.message
              : 'Identifiants invalides';
      },
    });
  }
}
