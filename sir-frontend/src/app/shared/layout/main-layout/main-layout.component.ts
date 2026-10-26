import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { NotificationService } from '../../../core/notifications/notification.service';
import {
  notificationEventLabel,
  notificationRelativeTime,
} from '../../../core/notifications/notification.utils';
import { MeResponse } from '../../models/auth.models';

interface NavItem {
  label: string;
  icon: string;
  route: string;
  enabled: boolean;
  exact?: boolean;
}

@Component({
  selector: 'sir-main-layout',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './main-layout.component.html',
  styleUrl: './main-layout.component.scss',
})
export class MainLayoutComponent implements OnDestroy {
  private readonly auth = inject(AuthService);
  private readonly notifications = inject(NotificationService);

  readonly user = this.auth.currentUser;
  readonly panelOpen = signal(false);
  /** Menu latéral en tiroir sous 1024 px (toujours visible au-delà). */
  readonly menuOpen = signal(false);
  readonly unreadCount = computed(() => this.notifications.unreadCount());
  readonly notificationItems = this.notifications.items;
  readonly eventLabel = notificationEventLabel;
  readonly relativeTime = notificationRelativeTime;

  readonly navItems = computed<NavItem[]>(() => {
    const canNotif = this.auth.hasRole(
      'ADMIN_SCR',
      'ADMIN_DISPATCHING',
      'ADMIN_SAQS',
      'DISPATCHER',
    );
    const items: NavItem[] = [
      { label: 'Tableau de bord', icon: 'dashboard', route: '/', enabled: true, exact: true },
      {
        label: 'Interruptions',
        icon: 'warning',
        route: '/interruptions/distribution',
        enabled: true,
      },
      { label: 'Workflow', icon: 'assignment', route: '/workflow/validation', enabled: true },
      { label: 'Assistant', icon: 'psychology', route: '/assistant', enabled: true },
      { label: 'Rapports', icon: 'assessment', route: '/rapports', enabled: true },
      { label: 'Administration', icon: 'admin_panel_settings', route: '/admin/referentiel', enabled: true },
      { label: 'Utilisateurs', icon: 'group', route: '/admin/utilisateurs', enabled: true },
    ];
    if (canNotif) {
      items.splice(5, 0, {
        label: 'Notifications',
        icon: 'sms',
        route: '/notifications/sms',
        enabled: true,
      });
    }
    return items;
  });

  constructor() {
    if (!this.auth.currentUser()) {
      this.auth.fetchMe().subscribe({
        next: () => this.notifications.connect(),
      });
    } else {
      this.notifications.connect();
    }
  }

  userInitials(user: MeResponse): string {
    const first = user.prenom?.charAt(0) ?? '';
    const last = user.nom?.charAt(0) ?? '';
    return `${first}${last}`.toUpperCase() || user.login.slice(0, 2).toUpperCase();
  }

  toggleNotifications(): void {
    const next = !this.panelOpen();
    this.panelOpen.set(next);
    if (next) {
      this.notifications.markAllRead();
    }
  }

  toggleMenu(): void {
    this.menuOpen.update((open) => !open);
  }

  closeMenu(): void {
    this.menuOpen.set(false);
  }

  closeNotifications(): void {
    this.panelOpen.set(false);
  }

  logout(): void {
    this.notifications.disconnect();
    this.auth.logout().subscribe();
  }

  ngOnDestroy(): void {
    this.notifications.disconnect();
  }
}
