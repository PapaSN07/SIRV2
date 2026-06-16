import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { from, of } from 'rxjs';
import { catchError, concatMap, finalize, toArray } from 'rxjs/operators';
import { Region } from '../../../shared/models/geo.models';
import {
  InterruptionDistribution,
  InterruptionDistributionDetail,
} from '../../../shared/models/interruption.models';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { GeoService } from '../../geo/services/geo.service';
import { InterruptionDistributionService } from '../../interruptions-distribution/services/interruption-distribution.service';

type PriorityLevel = 'critique' | 'elevee' | 'normale';

@Component({
  selector: 'sir-validation-queue',
  standalone: true,
  imports: [RouterLink, DatePipe, PaginatorComponent, StatusChipComponent],
  templateUrl: './validation-queue.component.html',
  styleUrl: './validation-queue.component.scss',
})
export class ValidationQueueComponent implements OnInit {
  private readonly service = inject(InterruptionDistributionService);
  private readonly geo = inject(GeoService);

  readonly pageSizeOptions = [10, 20, 50];

  readonly items = signal<InterruptionDistribution[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly regionId = signal<number | null>(null);
  readonly dateDebut = signal('');
  readonly dateFin = signal('');
  readonly searchQuery = signal('');
  readonly regions = signal<Region[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly actionMessage = signal<string | null>(null);
  readonly validating = signal(false);

  readonly selectedIds = signal<Set<number>>(new Set());
  readonly focusedId = signal<number | null>(null);
  readonly detail = signal<InterruptionDistributionDetail | null>(null);
  readonly detailLoading = signal(false);

  readonly filteredItems = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    if (!q) return this.items();
    return this.items().filter((item) => {
      const numero = String(item.numero_interruption);
      const loc = item.localisation?.toLowerCase() ?? '';
      return numero.includes(q) || loc.includes(q);
    });
  });

  readonly selectedCount = computed(() => this.selectedIds().size);

  readonly showBulkBar = computed(() => this.selectedCount() > 0 && !this.validating());

  ngOnInit(): void {
    this.geo.getRegions().subscribe({
      next: (r) => this.regions.set(r),
      error: () => {},
    });
    this.load();
  }

  priority(item: InterruptionDistribution): PriorityLevel {
    const mw = item.puissance_coupee_mw ?? 0;
    if (mw >= 5) return 'critique';
    if (mw >= 2) return 'elevee';
    return 'normale';
  }

  priorityLabel(level: PriorityLevel): string {
    switch (level) {
      case 'critique':
        return 'Critique';
      case 'elevee':
        return 'Élevée';
      default:
        return 'Normale';
    }
  }

  tensionLabel(kv: number | null): string {
    if (kv == null) return 'MT';
    if (kv >= 30) return 'HT';
    if (kv >= 15) return 'MT';
    return 'BT';
  }

  onRegionChange(value: string): void {
    this.regionId.set(value ? Number(value) : null);
    this.page.set(1);
    this.load();
  }

  onDateDebutChange(event: Event): void {
    this.dateDebut.set((event.target as HTMLInputElement).value);
  }

  onDateFinChange(event: Event): void {
    this.dateFin.set((event.target as HTMLInputElement).value);
  }

  onSearchChange(event: Event): void {
    this.searchQuery.set((event.target as HTMLInputElement).value);
  }

  applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  resetFilters(): void {
    this.regionId.set(null);
    this.dateDebut.set('');
    this.dateFin.set('');
    this.searchQuery.set('');
    this.page.set(1);
    this.load();
  }

  onPageChange(nextPage: number): void {
    this.page.set(nextPage);
    this.load();
  }

  onPageSizeChange(size: number): void {
    this.pageSize.set(size);
    this.page.set(1);
    this.load();
  }

  isSelected(id: number): boolean {
    return this.selectedIds().has(id);
  }

  allSelected(): boolean {
    const rows = this.filteredItems();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  }

  toggleSelect(id: number, event: Event): void {
    event.stopPropagation();
    const checked = (event.target as HTMLInputElement).checked;
    const next = new Set(this.selectedIds());
    if (checked) next.add(id);
    else next.delete(id);
    this.selectedIds.set(next);
  }

  toggleSelectAll(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    if (!checked) {
      this.selectedIds.set(new Set());
      return;
    }
    this.selectedIds.set(new Set(this.filteredItems().map((row) => row.id)));
  }

  clearSelection(): void {
    this.selectedIds.set(new Set());
  }

  selectRow(item: InterruptionDistribution): void {
    this.focusedId.set(item.id);
    this.loadDetail(item.id);
  }

  closeDetail(): void {
    this.focusedId.set(null);
    this.detail.set(null);
  }

  validateOne(id: number): void {
    this.actionError.set(null);
    this.validating.set(true);
    this.service.valider(id).subscribe({
      next: () => {
        this.actionMessage.set('Interruption validée.');
        if (this.focusedId() === id) {
          this.closeDetail();
        }
        const next = new Set(this.selectedIds());
        next.delete(id);
        this.selectedIds.set(next);
        this.load();
      },
      error: (err: Error) => {
        this.actionError.set(err.message);
        this.validating.set(false);
      },
    });
  }

  validateSelected(): void {
    const ids = [...this.selectedIds()];
    if (ids.length === 0) return;

    this.actionError.set(null);
    this.validating.set(true);

    from(ids)
      .pipe(
        concatMap((id) =>
          this.service.valider(id).pipe(
            catchError((err: Error) => of({ error: err.message, id })),
          ),
        ),
        toArray(),
        finalize(() => this.validating.set(false)),
      )
      .subscribe((results) => {
        const failures = results.filter((r) => 'error' in r) as { error: string; id: number }[];
        const successCount = ids.length - failures.length;
        if (failures.length === 0) {
          this.actionMessage.set(`${successCount} interruption(s) validée(s).`);
          this.selectedIds.set(new Set());
          this.closeDetail();
          this.load();
          return;
        }
        this.actionError.set(
          `${successCount} validée(s), ${failures.length} échec(s) : ${failures[0].error}`,
        );
        this.load();
      });
  }

  private loadDetail(id: number): void {
    this.detailLoading.set(true);
    this.service.get(id).subscribe({
      next: (d) => {
        this.detail.set(d);
        this.detailLoading.set(false);
      },
      error: (err: Error) => {
        this.actionError.set(err.message);
        this.detailLoading.set(false);
      },
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.service
      .list({
        page: this.page(),
        page_size: this.pageSize(),
        statut: 'cloture',
        region_id: this.regionId() ?? undefined,
        date_debut: this.dateDebut() ? `${this.dateDebut()}T00:00:00` : undefined,
        date_fin: this.dateFin() ? `${this.dateFin()}T23:59:59` : undefined,
      })
      .subscribe({
        next: (res) => {
          this.items.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
          this.validating.set(false);
          const focused = this.focusedId();
          if (focused && !res.items.some((i) => i.id === focused)) {
            this.closeDetail();
          }
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
          this.validating.set(false);
        },
      });
  }
}
