import { Component, OnInit, inject, signal } from '@angular/core';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { RoleDetail } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';

@Component({
  selector: 'sir-roles-list',
  standalone: true,
  imports: [PageHeaderComponent, AdminNavComponent],
  template: `
    <section class="admin-page">
      <sir-page-header title="Rôles et permissions" [breadcrumbs]="[{ label: 'Administration' }, { label: 'Rôles' }]" />
      <sir-admin-nav [showUsers]="false" />
      @if (error()) {
        <p class="alert">{{ error() }}</p>
      } @else {
        @for (role of roles(); track role.id) {
          <article class="role-card">
            <h2>{{ role.nom }}</h2>
            <p class="muted">{{ role.description }}</p>
            <ul>
              @for (p of role.permissions; track p.id) {
                <li><code>{{ p.ressource }}:{{ p.action }}</code> — {{ p.description }}</li>
              }
            </ul>
          </article>
        }
      }
    </section>
  `,
  styles: [
    `
      .admin-page { max-width: 960px; margin: 0 auto; }
      .role-card { background: #fff; border: 1px solid #c4c7cf; border-radius: 0.25rem; padding: 1rem; margin-bottom: 1rem; }
      .muted { color: #414750; font-size: 13px; }
      .alert { padding: 0.75rem; background: #ffdad6; color: #93000a; border-radius: 0.25rem; }
      ul { margin: 0.5rem 0 0; padding-left: 1.25rem; font-size: 13px; }
    `,
  ],
})
export class RolesListComponent implements OnInit {
  private readonly admin = inject(AdminAdvancedService);
  readonly roles = signal<RoleDetail[]>([]);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.admin.listRoles().subscribe({
      next: (items) => this.roles.set(items),
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
