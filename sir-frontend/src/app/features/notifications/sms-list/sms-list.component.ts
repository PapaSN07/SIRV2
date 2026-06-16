import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { NotificationSmsService } from '../services/notification-sms.service';
import { SmsEnvoye } from '../../../shared/models/notification.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { NotificationsNavComponent } from '../../../shared/ui/notifications-nav/notifications-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'sir-sms-list',
  standalone: true,
  imports: [DatePipe, RouterLink, PageHeaderComponent, NotificationsNavComponent, PaginatorComponent],
  templateUrl: './sms-list.component.html',
  styleUrl: './sms-list.component.scss',
})
export class SmsListComponent implements OnInit {
  private readonly sms = inject(NotificationSmsService);
  private readonly auth = inject(AuthService);

  readonly pageSize = 20;
  readonly items = signal<SmsEnvoye[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly statut = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selected = signal<SmsEnvoye | null>(null);

  readonly canSend = computed(() =>
    this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS'),
  );

  ngOnInit(): void {
    this.load();
  }

  onStatutChange(value: string): void {
    this.statut.set(value);
    this.page.set(1);
    this.load();
  }

  onPageChange(next: number): void {
    this.page.set(next);
    this.load();
  }

  openDetail(item: SmsEnvoye): void {
    this.selected.set(item);
  }

  closeDetail(): void {
    this.selected.set(null);
  }

  statutLabel(statut: string): string {
    const map: Record<string, string> = {
      en_attente: 'En attente',
      envoye: 'Envoyé',
      echec: 'Échec',
    };
    return map[statut] ?? statut;
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.sms
      .list({
        page: this.page(),
        page_size: this.pageSize,
        statut: this.statut() || undefined,
      })
      .subscribe({
        next: (res) => {
          this.items.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
  }
}
