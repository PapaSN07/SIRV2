import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin, map, Observable, of, switchMap } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { Service, Region } from '../../../shared/models/geo.models';
import {
  InterruptionDistribution,
  InterruptionDistributionStats,
  OuvertureInterruption,
} from '../../../shared/models/interruption.models';
import { ReferentielItem } from '../../../shared/models/referentiel.models';
import { Feeder } from '../../../shared/models/reseau.models';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { ReferentielService } from '../../referentiel/services/referentiel.service';
import { GeoService } from '../../geo/services/geo.service';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';

type FilterChipKey =
  | 'region'
  | 'service'
  | 'feeder'
  | 'nature'
  | 'ouverture'
  | 'dateDebut'
  | 'dateFin';

interface FilterChip {
  key: FilterChipKey;
  label: string;
}

const DATE_FILTER_HINT =
  'Laissez vide pour afficher toutes les dates de votre périmètre.';

@Component({
  selector: 'sir-interruption-list',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
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
  private readonly referentiel = inject(ReferentielService);
  private readonly auth = inject(AuthService);

  readonly pageSizeOptions = [10, 20, 50];
  readonly dateFilterHint = DATE_FILTER_HINT;
  readonly ouvertureOptions: { value: OuvertureInterruption | ''; label: string }[] = [
    { value: '', label: 'Toutes' },
    { value: 'ouvert', label: 'Ouvertes' },
    { value: 'ferme', label: 'Fermées' },
  ];

  readonly items = signal<InterruptionDistribution[]>([]);
  readonly total = signal(0);
  readonly stats = signal<InterruptionDistributionStats | null>(null);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly regionId = signal<number | null>(null);
  readonly serviceId = signal<number | null>(null);
  readonly feederId = signal<number | null>(null);
  readonly natureId = signal<number | null>(null);
  readonly ouverture = signal<OuvertureInterruption | null>(null);
  readonly dateDebut = signal('');
  readonly dateFin = signal('');
  readonly regions = signal<Region[]>([]);
  readonly services = signal<Service[]>([]);
  readonly feeders = signal<Feeder[]>([]);
  readonly natures = signal<ReferentielItem[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly emptyFilterHint = signal<string | null>(null);
  readonly selectedIds = signal<Set<number>>(new Set());

  readonly isBrc = computed(() => this.auth.isExactRole('BRC'));
  readonly isBcc = computed(() => this.auth.isExactRole('BCC'));
  readonly isRegionalScope = computed(() => this.isBcc() || this.isBrc());
  readonly showServiceFilter = computed(() => this.isRegionalScope() || (!this.isBcc() && !this.isBrc()));

  readonly hasActiveFilters = computed(
    () =>
      this.regionId() !== null ||
      this.serviceId() !== null ||
      this.feederId() !== null ||
      this.natureId() !== null ||
      this.ouverture() !== null ||
      !!this.dateDebut() ||
      !!this.dateFin(),
  );

  readonly activeFilterChips = computed<FilterChip[]>(() => {
    const chips: FilterChip[] = [];
    const region = this.regions().find((r) => r.id === this.regionId());
    if (region) chips.push({ key: 'region', label: `Région : ${region.libelle}` });
    const svc = this.services().find((s) => s.id === this.serviceId());
    if (svc) chips.push({ key: 'service', label: `Service : ${svc.libelle}` });
    const feeder = this.feeders().find((f) => f.id === this.feederId());
    if (feeder) chips.push({ key: 'feeder', label: `Feeder : ${feeder.libelle}` });
    const nature = this.natures().find((n) => n.id === this.natureId());
    if (nature) chips.push({ key: 'nature', label: `Nature : ${nature.libelle}` });
    if (this.ouverture()) {
      const label = this.ouverture() === 'ouvert' ? 'Ouvertes' : 'Fermées';
      chips.push({ key: 'ouverture', label: `Ouverture : ${label}` });
    }
    if (this.dateDebut()) chips.push({ key: 'dateDebut', label: `Début : ${this.dateDebut()}` });
    if (this.dateFin()) chips.push({ key: 'dateFin', label: `Fin : ${this.dateFin()}` });
    return chips;
  });

  ngOnInit(): void {
    this.referentiel.list('natures', { page_size: 100 }).subscribe({
      next: (res) => this.natures.set(res.items),
      error: () => {},
    });

    this.geo.getRegions().subscribe({
      next: (r) => {
        this.regions.set(r);
        this.initScopeFromUser();
      },
      error: () => this.initScopeFromUser(),
    });
  }

  canCreate(): boolean {
    return this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR');
  }

  canValidate(): boolean {
    return this.auth.hasRole('SUPERVISEUR', 'ADMIN_SCR');
  }

  regionSelectDisabled(): boolean {
    return this.isRegionalScope();
  }

  onRegionChange(value: string): void {
    const region = value ? Number(value) : null;
    this.regionId.set(region);
    this.serviceId.set(null);
    this.feederId.set(null);
    this.loadServices(region);
    this.loadFeeders(region);
  }

  onServiceChange(value: string): void {
    this.serviceId.set(value ? Number(value) : null);
  }

  onFeederChange(value: string): void {
    this.feederId.set(value ? Number(value) : null);
  }

  onNatureChange(value: string): void {
    this.natureId.set(value ? Number(value) : null);
  }

  onOuvertureChange(value: string): void {
    this.ouverture.set(value ? (value as OuvertureInterruption) : null);
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
    const lockedRegion = this.isRegionalScope() ? this.regionId() : null;
    this.regionId.set(lockedRegion);
    this.serviceId.set(null);
    this.feederId.set(null);
    this.natureId.set(null);
    this.ouverture.set(null);
    this.dateDebut.set('');
    this.dateFin.set('');
    this.page.set(1);
    this.loadServices(lockedRegion);
    this.loadFeeders(lockedRegion);
    this.load();
  }

  removeFilter(key: FilterChipKey): void {
    switch (key) {
      case 'region':
        if (!this.isRegionalScope()) {
          this.regionId.set(null);
          this.serviceId.set(null);
          this.feederId.set(null);
          this.services.set([]);
          this.loadFeeders(null);
        }
        break;
      case 'service':
        this.serviceId.set(null);
        break;
      case 'feeder':
        this.feederId.set(null);
        break;
      case 'nature':
        this.natureId.set(null);
        break;
      case 'ouverture':
        this.ouverture.set(null);
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

  private initScopeFromUser(): void {
    const user = this.auth.currentUser();
    if (this.isRegionalScope() && user?.service_id) {
      this.regionId.set(user.service_id);
      this.loadServices(user.service_id);
      this.loadFeeders(user.service_id);
      this.load();
      return;
    }
    this.loadFeeders(null);
    this.load();
  }

  private loadServices(regionId: number | null): void {
    if (regionId === null) {
      this.services.set([]);
      return;
    }
    this.geo.getServicesByRegion(regionId).subscribe({
      next: (items) => this.services.set(items),
      error: () => this.services.set([]),
    });
  }

  private loadFeeders(regionId: number | null): void {
    this.fetchAllFeeders(regionId).subscribe({
      next: (items) => this.feeders.set(items),
      error: () => {},
    });
  }

  private fetchAllFeeders(regionId: number | null): Observable<Feeder[]> {
    const params = {
      page_size: 100,
      ...(regionId !== null ? { region_id: regionId } : {}),
    };

    return this.reseau.listFeeders({ page: 1, ...params }).pipe(
      switchMap((first) => {
        const totalPages = Math.ceil(first.total / first.page_size);
        if (totalPages <= 1) {
          return of(first.items);
        }
        const extraPages = Array.from({ length: totalPages - 1 }, (_, i) => i + 2);
        return forkJoin(
          extraPages.map((page) => this.reseau.listFeeders({ page, ...params })),
        ).pipe(map((pages) => [...first.items, ...pages.flatMap((p) => p.items)]));
      }),
    );
  }

  private listParams() {
    const dateDebut = this.dateDebut();
    const dateFin = this.dateFin();
    return {
      page: this.page(),
      page_size: this.pageSize(),
      region_id: this.regionId() ?? undefined,
      service_id: this.serviceId() ?? undefined,
      feeder_id: this.feederId() ?? undefined,
      nature_id: this.natureId() ?? undefined,
      ouverture: this.ouverture() ?? undefined,
      date_debut: dateDebut ? `${dateDebut}T00:00:00` : undefined,
      date_fin: dateFin ? `${dateFin}T23:59:59` : undefined,
    };
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.emptyFilterHint.set(null);
    this.selectedIds.set(new Set());

    const params = this.listParams();
    const dateDebut = this.dateDebut();
    const dateFin = this.dateFin();

    forkJoin({
      list: this.service.list(params),
      stats: this.service.stats(params),
    }).subscribe({
      next: ({ list: res, stats }) => {
        this.items.set(res.items);
        this.total.set(res.total);
        this.stats.set(stats);
        this.loading.set(false);
        if (res.total === 0 && this.hasActiveFilters()) {
          this.emptyFilterHint.set(this.buildEmptyFilterHint(dateDebut, dateFin));
        }
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }

  private buildEmptyFilterHint(dateDebut: string, dateFin: string): string {
    const parts: string[] = ['Aucun résultat pour ces critères.'];
    if (dateDebut || dateFin) {
      parts.push('Élargissez la période ou réinitialisez les filtres.');
    }
    if (this.regionId() && this.feederId()) {
      parts.push('Vérifiez que le feeder appartient bien à la région sélectionnée.');
    }
    return parts.join(' ');
  }
}
