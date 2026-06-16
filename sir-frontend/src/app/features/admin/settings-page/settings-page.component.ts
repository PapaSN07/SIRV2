import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { AppSettings } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';

@Component({
  selector: 'sir-settings-page',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent],
  template: `
    <section class="admin-page">
      <sir-page-header title="Paramètres application" [breadcrumbs]="[{ label: 'Administration' }, { label: 'Paramètres' }]" />
      <sir-admin-nav [showUsers]="false" />
      @if (error()) {
        <p class="alert">{{ error() }}</p>
      } @else {
        @if (settings(); as s) {
          <div class="settings-panel">
            <p><strong>Environnement :</strong> {{ s.environment }}</p>
            <p><strong>SMS Gateway :</strong> {{ s.sms_gateway_url || '— (mode mock)' }}</p>
            <p><strong>SMTP :</strong> {{ s.smtp_host || '—' }}:{{ s.smtp_port }}</p>
            @if (canWrite()) {
              <label class="field">
                <span>Seuil fugitif (minutes)</span>
                <input type="number" min="1" max="120" [(ngModel)]="seuilFugitif" />
              </label>
              <button type="button" class="sir-btn sir-btn--primary" [disabled]="saving()" (click)="save()">
                {{ saving() ? 'Enregistrement…' : 'Enregistrer' }}
              </button>
            } @else {
              <p><strong>Seuil fugitif :</strong> {{ s.seuil_fugitif_minutes }} min</p>
            }
          </div>
        }
      }
    </section>
  `,
  styles: [
    `
      .admin-page { max-width: 640px; margin: 0 auto; }
      .settings-panel { background: #fff; border: 1px solid #c4c7cf; border-radius: 0.25rem; padding: 1.25rem; }
      .field { display: flex; flex-direction: column; gap: 0.25rem; margin: 1rem 0; }
      .alert { padding: 0.75rem; background: #ffdad6; color: #93000a; }
    `,
  ],
})
export class SettingsPageComponent implements OnInit {
  private readonly admin = inject(AdminAdvancedService);
  private readonly auth = inject(AuthService);

  readonly settings = signal<AppSettings | null>(null);
  readonly error = signal<string | null>(null);
  readonly saving = signal(false);
  seuilFugitif = 5;

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING'));

  ngOnInit(): void {
    this.admin.getSettings().subscribe({
      next: (s) => {
        this.settings.set(s);
        this.seuilFugitif = s.seuil_fugitif_minutes;
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }

  save(): void {
    this.saving.set(true);
    this.admin.updateSettings({ seuil_fugitif_minutes: this.seuilFugitif }).subscribe({
      next: (s) => {
        this.settings.set(s);
        this.saving.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.saving.set(false);
      },
    });
  }
}
