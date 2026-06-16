import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { AuditLogEntry } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

@Component({
  selector: 'sir-audit-log-list',
  standalone: true,
  imports: [DatePipe, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  template: `
    <section class="admin-page">
      <sir-page-header title="Journal d'audit" [breadcrumbs]="[{ label: 'Administration' }, { label: 'Audit' }]" />
      <sir-admin-nav [showUsers]="false" />
      @if (error()) {
        <p class="alert">{{ error() }}</p>
      } @else {
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Date</th><th>Table</th><th>Action</th><th>Utilisateur</th></tr>
            </thead>
            <tbody>
              @for (row of items(); track row.id) {
                <tr>
                  <td>{{ row.created_at | date: 'dd/MM/yyyy HH:mm' }}</td>
                  <td>{{ row.table_name }} #{{ row.record_id }}</td>
                  <td>{{ row.action }}</td>
                  <td>{{ row.user_login ?? row.user_id }}</td>
                </tr>
              } @empty {
                <tr><td colspan="4">Aucune entrée.</td></tr>
              }
            </tbody>
          </table>
        </div>
        <sir-paginator [total]="total()" [page]="page()" [pageSize]="pageSize" (pageChange)="onPageChange($event)" />
      }
    </section>
  `,
  styles: [
    `
      .admin-page { max-width: 1200px; margin: 0 auto; }
      .table-wrap { background: #fff; border: 1px solid #c4c7cf; margin-bottom: 1rem; overflow-x: auto; }
      .data-table { width: 100%; border-collapse: collapse; th, td { padding: 0.75rem 1rem; border-bottom: 1px solid #c4c7cf; text-align: left; } }
      .alert { padding: 0.75rem; background: #ffdad6; color: #93000a; }
    `,
  ],
})
export class AuditLogListComponent implements OnInit {
  private readonly admin = inject(AdminAdvancedService);
  readonly pageSize = 20;
  readonly items = signal<AuditLogEntry[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.load();
  }

  onPageChange(next: number): void {
    this.page.set(next);
    this.load();
  }

  private load(): void {
    this.admin.listAuditLog(this.page(), this.pageSize).subscribe({
      next: (res) => {
        this.items.set(res.items);
        this.total.set(res.total);
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }
}
