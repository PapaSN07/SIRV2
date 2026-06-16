import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { NaptService } from '../services/napt.service';
import { NaptItem } from '../../../shared/models/napt.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

@Component({
  selector: 'sir-napt-list',
  standalone: true,
  imports: [DatePipe, FormsModule, PageHeaderComponent, PaginatorComponent],
  templateUrl: './napt-list.component.html',
  styleUrl: './napt-list.component.scss',
})
export class NaptListComponent implements OnInit {
  private readonly napt = inject(NaptService);
  private readonly auth = inject(AuthService);

  readonly pageSize = 20;
  readonly items = signal<NaptItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly statut = signal('');
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selected = signal<NaptItem | null>(null);

  readonly canWrite = computed(() => this.auth.hasRole('BCC', 'ADMIN_SCR'));
  readonly canValidate = computed(() =>
    this.auth.hasRole('SUPERVISEUR', 'ADMIN_SCR', 'ADMIN_SAQS'),
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

  openDetail(item: NaptItem): void {
    this.selected.set(item);
  }

  closeDetail(): void {
    this.selected.set(null);
  }

  runAction(action: 'soumettre' | 'valider' | 'cloturer', item: NaptItem): void {
    const call =
      action === 'soumettre'
        ? this.napt.soumettre(item.id)
        : action === 'valider'
          ? this.napt.valider(item.id)
          : this.napt.cloturer(item.id);
    call.subscribe({
      next: (updated) => {
        this.selected.set(updated);
        this.load();
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.napt.list(this.page(), this.pageSize, this.statut() || undefined).subscribe({
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
