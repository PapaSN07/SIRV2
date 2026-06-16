import { Component, Input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-admin-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="admin-nav" aria-label="Administration">
      @if (showReferentiel) {
        <a
          class="admin-nav__tab"
          routerLink="/admin/referentiel"
          routerLinkActive="admin-nav__tab--active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          Référentiels
        </a>
      }
      @if (showReseauDist) {
        <a
          class="admin-nav__tab"
          routerLink="/admin/reseau/distribution"
          routerLinkActive="admin-nav__tab--active"
        >
          Réseau distribution
        </a>
      }
      @if (showReseauTrans) {
        <a
          class="admin-nav__tab"
          routerLink="/admin/reseau/transport"
          routerLinkActive="admin-nav__tab--active"
        >
          Réseau transport
        </a>
      }
      @if (showUsers) {
        <a
          class="admin-nav__tab"
          routerLink="/admin/utilisateurs"
          routerLinkActive="admin-nav__tab--active"
          [routerLinkActiveOptions]="{ exact: true }"
        >
          Utilisateurs
        </a>
      }
      @if (showAdvanced) {
        <a class="admin-nav__tab" routerLink="/admin/roles" routerLinkActive="admin-nav__tab--active">
          Rôles
        </a>
        <a class="admin-nav__tab" routerLink="/admin/audit-log" routerLinkActive="admin-nav__tab--active">
          Audit
        </a>
        <a class="admin-nav__tab" routerLink="/admin/settings" routerLinkActive="admin-nav__tab--active">
          Paramètres
        </a>
      }
    </nav>
  `,
  styles: [
    `
      .admin-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        margin-bottom: 1rem;
        padding: 0.25rem;
        background: #eef4fd;
        border-radius: 0.5rem;
      }
      .admin-nav__tab {
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        font-size: 13px;
        font-weight: 600;
        color: #414750;
        text-decoration: none;
      }
      .admin-nav__tab:hover {
        color: #3d49a0;
      }
      .admin-nav__tab--active {
        background: #fff;
        color: #3d49a0;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      }
    `,
  ],
})
export class AdminNavComponent {
  @Input() showReferentiel = true;
  @Input() showReseauDist = true;
  @Input() showReseauTrans = true;
  @Input() showUsers = true;
  @Input() showAdvanced = true;
}
