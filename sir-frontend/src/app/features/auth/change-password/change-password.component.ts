import { Component, OnInit, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';

@Component({
  selector: 'sir-change-password',
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './change-password.component.html',
  styleUrl: './change-password.component.scss',
})
export class ChangePasswordComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  loading = false;
  errorMessage = '';
  hideCurrent = true;
  hideNew = true;
  hideConfirm = true;

  readonly form = this.fb.nonNullable.group({
    login: ['', Validators.required],
    current_password: ['', Validators.required],
    new_password: ['', [Validators.required, Validators.minLength(8)]],
    confirm_password: ['', Validators.required],
  });

  ngOnInit(): void {
    const login = this.route.snapshot.queryParamMap.get('login');
    if (login) {
      this.form.patchValue({ login });
    }
  }

  onSubmit(): void {
    if (this.form.invalid) return;

    const { login, current_password, new_password, confirm_password } = this.form.getRawValue();
    if (new_password !== confirm_password) {
      this.errorMessage = 'Les mots de passe ne correspondent pas.';
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    this.auth.changePassword({ login, current_password, new_password }).subscribe({
      next: () => {
        this.loading = false;
        void this.router.navigate(['/']);
      },
      error: (err: { error?: { detail?: { error?: string | { message?: string } } } }) => {
        this.loading = false;
        const detail = err.error?.detail?.error;
        this.errorMessage =
          typeof detail === 'string'
            ? detail
            : typeof detail === 'object' && detail?.message
              ? detail.message
              : 'Impossible de changer le mot de passe.';
      },
    });
  }
}
