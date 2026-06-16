import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { NotificationDestinataireService } from '../services/notification-destinataire.service';
import { Destinataire, DestinataireCreate } from '../../../shared/models/notification.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { NotificationsNavComponent } from '../../../shared/ui/notifications-nav/notifications-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

interface DestForm {
  nom: string;
  telephone: string;
  email: string;
  is_active: boolean;
}

@Component({
  selector: 'sir-destinataires-list',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, NotificationsNavComponent, PaginatorComponent],
  templateUrl: './destinataires-list.component.html',
  styleUrl: './destinataires-list.component.scss',
})
export class DestinatairesListComponent implements OnInit {
  private readonly service = inject(NotificationDestinataireService);
  private readonly auth = inject(AuthService);

  readonly pageSize = 20;
  readonly items = signal<Destinataire[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly form = signal<DestForm>(this.emptyForm());

  readonly canWrite = computed(() =>
    this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS'),
  );

  ngOnInit(): void {
    this.load();
  }

  onPageChange(next: number): void {
    this.page.set(next);
    this.load();
  }

  openCreate(): void {
    this.editingId.set(null);
    this.form.set(this.emptyForm());
    this.formOpen.set(true);
    this.error.set(null);
  }

  openEdit(item: Destinataire): void {
    this.editingId.set(item.id);
    this.form.set({
      nom: item.nom,
      telephone: item.telephone ?? '',
      email: item.email ?? '',
      is_active: item.is_active,
    });
    this.formOpen.set(true);
    this.error.set(null);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  patchForm(key: keyof DestForm, value: string | boolean): void {
    this.form.update((f) => ({ ...f, [key]: value }));
  }

  save(): void {
    const f = this.form();
    if (!f.nom.trim()) {
      this.error.set('Le nom est obligatoire.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);

    const id = this.editingId();
    if (id) {
      this.service
        .update(id, {
          nom: f.nom.trim(),
          telephone: f.telephone.trim() || null,
          email: f.email.trim() || null,
          is_active: f.is_active,
        })
        .subscribe({
          next: () => {
            this.saving.set(false);
            this.closeForm();
            this.load();
          },
          error: (err: Error) => {
            this.error.set(err.message);
            this.saving.set(false);
          },
        });
    } else {
      const body: DestinataireCreate = {
        nom: f.nom.trim(),
        telephone: f.telephone.trim() || null,
        email: f.email.trim() || null,
      };
      this.service.create(body).subscribe({
        next: () => {
          this.saving.set(false);
          this.closeForm();
          this.load();
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
    }
  }

  deactivate(item: Destinataire): void {
    if (!confirm(`Désactiver le destinataire « ${item.nom} » ?`)) return;
    this.service.delete(item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.service.listDestinataires(this.page(), this.pageSize).subscribe({
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

  private emptyForm(): DestForm {
    return { nom: '', telephone: '', email: '', is_active: true };
  }
}
