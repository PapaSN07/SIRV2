import { Component, Input, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { FONCTIONNALITES } from '../../../core/config/fonctionnalites';

interface AdminTab {
  route: string;
  label: string;
  icon: string;
  exact?: boolean;
}

/**
 * Sous-menu de l'Administration : mêmes onglets sur toutes les pages (selon les droits du compte),
 * l'onglet de la page affichée est en surbrillance.
 */
@Component({
  selector: 'sir-admin-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="sir-tabs" aria-label="Administration">
      @for (tab of tabs(); track tab.route) {
        <a
          class="sir-tab"
          [routerLink]="tab.route"
          routerLinkActive="sir-tab--active"
          [routerLinkActiveOptions]="{ exact: tab.exact ?? false }"
          ariaCurrentWhenActive="page"
        >
          <span class="material-symbols-outlined" aria-hidden="true">{{ tab.icon }}</span>
          {{ tab.label }}
        </a>
      }
    </nav>
  `,
})
export class AdminNavComponent {
  private readonly auth = inject(AuthService);

  /** Entrées conservées pour compatibilité : les onglets suivent désormais les droits du compte. */
  @Input() showReferentiel = true;
  @Input() showReseauDist = true;
  @Input() showReseauTrans = true;
  @Input() showUsers = true;
  @Input() showAdvanced = true;

  readonly tabs = computed<AdminTab[]>(() => {
    this.auth.currentUser();
    const tabs: AdminTab[] = [
      { route: '/admin/referentiel', label: 'Référentiels', icon: 'list_alt', exact: true },
    ];
    if (this.auth.hasRole('ADMIN_SCR', 'BCC', 'BRC', 'ADMIN_SAQS', 'SUPERVISEUR') || this.auth.hasPermission('reseau:read')) {
      tabs.push({ route: '/admin/reseau/distribution', label: 'Réseau distribution', icon: 'lan' });
    }
    if (FONCTIONNALITES.transport && this.auth.hasRole('ADMIN_DISPATCHING', 'DISPATCHER', 'ADMIN_SAQS')) {
      tabs.push({ route: '/admin/reseau/transport', label: 'Réseau transport', icon: 'electric_bolt' });
    }
    if (this.auth.hasRole('ADMIN_SCR', 'ADMIN_SAQS')) {
      tabs.push({ route: '/admin/objectifs', label: 'Objectifs', icon: 'flag' });
    }
    if (this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING') || this.auth.hasPermission('admin_utilisateurs:read')) {
      tabs.push({ route: '/admin/utilisateurs', label: 'Utilisateurs', icon: 'group', exact: true });
    }
    if (this.auth.hasPermission('admin_roles:read') || this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING')) {
      tabs.push({ route: '/admin/roles', label: 'Rôles et droits', icon: 'admin_panel_settings' });
    }
    if (this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING')) {
      tabs.push(
        { route: '/admin/audit-log', label: 'Journal', icon: 'history' },
        { route: '/admin/settings', label: 'Paramètres', icon: 'settings' },
      );
    }
    return tabs;
  });
}
