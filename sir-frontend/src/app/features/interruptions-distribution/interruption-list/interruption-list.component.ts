import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { Region } from '../../../shared/models/geo.models';
import {
  InterruptionDistribution,
  StatutInterruption,
} from '../../../shared/models/interruption.models';
import { Feeder } from '../../../shared/models/reseau.models';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { STATUTS_INTERRUPTION, statutLabel } from '../../../shared/utils/statut.utils';
import { GeoService } from '../../geo/services/geo.service';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';

type FilterChipKey = 'region' | 'feeder' | 'statut' | 'dateDebut' | 'dateFin';

interface FilterChip {
  key: FilterChipKey;
  label: string;
}

@Component({
  selector: 'sir-interruption-list',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    DecimalPipe,
    PageHeaderComponent,
    StatusChipComponent,
    PaginatorComponent,
    InterruptionsNavComponent,
  ],
  templateUrl: './interruption-list.component.html',
  styleUrl: './interruption-list.component.scss',
})
export class InterruptionListComponent implements OnInit {
  private readonly service = inject(InterruptionDistributionService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly geo = inject(GeoService);
  private readonly auth = inject(AuthService);

  readonly statuts = STATUTS_INTERRUPTION;
  readonly statutLabel = statutLabel;
  readonly pageSizeOptions = [10, 20, 50];

  readonly items = signal<InterruptionDistribution[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly regionId = signal<number | null>(null);
  readonly feederId = signal<number | null>(null);
  readonly statut = signal<StatutInterruption | null>(null);
  readonly dateDebut = signal('');
  readonly dateFin = signal('');
  readonly regions = signal<Region[]>([]);
  readonly feeders = signal<Feeder[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selectedIds = signal<Set<number>>(new Set());

  readonly totalEndPage = computed(() =>
    this.items().reduce((sum, item) => sum + (item.end_mwh ?? 0), 0),
  );

  readonly avgDurationPage = computed(() => {
    const durations = this.items().map((item) => item.duree_minutes).filter((v): v is number => v != null);
    if (durations.length === 0) return 0;
    return Math.round(durations.reduce((a, b) => a + b, 0) / durations.length);
  });

  readonly activeCount = computed(() => this.items().filter((item) => item.statut === 'en_cours').length);

  readonly activeFilterChips = computed<FilterChip[]>(() => {
    const chips: FilterChip[] = [];
    const region = this.regions().find((r) => r.id === this.regionId());
    if (region) chips.push({ key: 'region', label: `Région : ${region.libelle}` });
    const feeder = this.feeders().find((f) => f.id === this.feederId());
    if (feeder) chips.push({ key: 'feeder', label: `Feeder : ${feeder.libelle}` });
    if (this.statut()) chips.push({ key: 'statut', label: `Statut : ${statutLabel(this.statut()!)}` });
    if (this.dateDebut()) chips.push({ key: 'dateDebut', label: `Début : ${this.dateDebut()}` });
    if (this.dateFin()) chips.push({ key: 'dateFin', label: `Fin : ${this.dateFin()}` });
    return chips;
  });

  ngOnInit(): void {
    this.geo.getRegions().subscribe({
      next: (r) => this.regions.set(r),
      error: () => {},
    });
    this.loadFeeders();
    this.load();
  }

  canCreate(): boolean {
    return this.auth.hasRole('BCC', 'ADMIN_SCR');
  }

  canValidate(): boolean {
    return this.auth.hasRole('SUPERVISEUR', 'ADMIN_SCR');
  }

  onRegionChange(value: string): void {
    this.regionId.set(value ? Number(value) : null);
  }

  onFeederChange(value: string): void {
    this.feederId.set(value ? Number(value) : null);
  }

  onStatutChange(value: string): void {
    this.statut.set(value ? (value as StatutInterruption) : null);
  }

  onDateDebutChange(event: Event): void {
    this.dateDebut.set((event.target as HTMLInputElement).value);
  }

  onDateFinChange(event: Event): void {
    this.dateFin.set((event.target as HTMLInputElement).value);
  }

  applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  resetFilters(): void {
    this.regionId.set(null);
    this.feederId.set(null);
    this.statut.set(null);
    this.dateDebut.set('');
    this.dateFin.set('');
    this.page.set(1);
    this.load();
  }

  removeFilter(key: FilterChipKey): void {
    switch (key) {
      case 'region':
        this.regionId.set(null);
        break;
      case 'feeder':
        this.feederId.set(null);
        break;
      case 'statut':
        this.statut.set(null);
        break;
      case 'dateDebut':
        this.dateDebut.set('');
        break;
      case 'dateFin':
        this.dateFin.set('');
        break;
    }
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
    const rows = this.items();
    return rows.length > 0 && rows.every((row) => this.selectedIds().has(row.id));
  }

  toggleSelect(id: number, event: Event): void {
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
    this.selectedIds.set(new Set(this.items().map((row) => row.id)));
  }

  onRowClick(event: Event, id: number): void {
    const target = event.target as HTMLElement;
    if (target.closest('a, button, input')) return;
    const next = new Set(this.selectedIds());
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.selectedIds.set(next);
  }

  private loadFeeders(): void {
    this.reseau.listFeeders({ page: 1, page_size: 100 }).subscribe({
      next: (res) => this.feeders.set(res.items),
      error: () => {},
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.selectedIds.set(new Set());

    this.service
      .list({
        page: this.page(),
        page_size: this.pageSize(),
        region_id: this.regionId() ?? undefined,
        feeder_id: this.feederId() ?? undefined,
        statut: this.statut() ?? undefined,
        date_debut: this.dateDebut() ? `${this.dateDebut()}T00:00:00` : undefined,
        date_fin: this.dateFin() ? `${this.dateFin()}T23:59:59` : undefined,
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
