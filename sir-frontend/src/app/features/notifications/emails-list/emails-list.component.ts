import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { NotificationDestinataireService } from '../services/notification-destinataire.service';
import { EmailEnvoye } from '../../../shared/models/notification.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { NotificationsNavComponent } from '../../../shared/ui/notifications-nav/notifications-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

@Component({
  selector: 'sir-emails-list',
  standalone: true,
  imports: [DatePipe, PageHeaderComponent, NotificationsNavComponent, PaginatorComponent],
  templateUrl: './emails-list.component.html',
  styleUrl: './emails-list.component.scss',
})
export class EmailsListComponent implements OnInit {
  private readonly service = inject(NotificationDestinataireService);

  readonly pageSize = 20;
  readonly items = signal<EmailEnvoye[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly statut = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selected = signal<EmailEnvoye | null>(null);

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

  openDetail(item: EmailEnvoye): void {
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
    this.service
      .listEmails({
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
