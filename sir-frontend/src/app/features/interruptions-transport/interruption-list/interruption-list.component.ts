import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import {
  InterruptionTransport,
  StatutInterruption,
  TypeDirectionTransport,
} from '../../../shared/models/interruption-transport.models';
import { EquipementTransport } from '../../../shared/models/reseau-transport.models';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { STATUTS_INTERRUPTION, statutLabel } from '../../../shared/utils/statut.utils';
import { InterruptionTransportService } from '../services/interruption-transport.service';
import { ReseauTransportService } from '../services/reseau-transport.service';

type FilterChipKey = 'typeDirection' | 'equipement' | 'statut' | 'dateDebut' | 'dateFin';

interface FilterChip {
  key: FilterChipKey;
  label: string;
}

@Component({
  selector: 'sir-interruption-transport-list',
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
export class InterruptionTransportListComponent implements OnInit {
  private readonly service = inject(InterruptionTransportService);
  private readonly reseau = inject(ReseauTransportService);
  private readonly auth = inject(AuthService);

  readonly statuts = STATUTS_INTERRUPTION;
  readonly statutLabel = statutLabel;
  readonly pageSizeOptions = [10, 20, 50];
  readonly typeDirections: TypeDirectionTransport[] = ['transport', 'omvg'];

  readonly items = signal<InterruptionTransport[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(20);
  readonly typeDirection = signal<TypeDirectionTransport | null>(null);
  readonly equipementId = signal<number | null>(null);
  readonly statut = signal<StatutInterruption | null>(null);
  readonly dateDebut = signal('');
  readonly dateFin = signal('');
  readonly equipements = signal<EquipementTransport[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly selectedIds = signal<Set<number>>(new Set());

  readonly totalEndPage = computed(() =>
    this.items().reduce(
      (sum, item) => sum + (item.energie_non_fournie_mwh ?? item.puissance_coupee_mw ?? 0),
      0,
    ),
  );

  readonly avgDurationPage = computed(() => {
    const durations = this.items().map((item) => item.duree_minutes).filter((v): v is number => v != null);
    if (durations.length === 0) return 0;
    return Math.round(durations.reduce((a, b) => a + b, 0) / durations.length);
  });

  readonly activeCount = computed(() => this.items().filter((item) => item.statut === 'en_cours').length);

  readonly activeFilterChips = computed<FilterChip[]>(() => {
    const chips: FilterChip[] = [];
    if (this.typeDirection()) {
      chips.push({
        key: 'typeDirection',
        label: `Type : ${this.typeDirectionLabel(this.typeDirection()!)}`,
      });
    }
    const eq = this.equipements().find((e) => e.id === this.equipementId());
    if (eq) chips.push({ key: 'equipement', label: `Équipement : ${eq.libelle}` });
    if (this.statut()) chips.push({ key: 'statut', label: `Statut : ${statutLabel(this.statut()!)}` });
    if (this.dateDebut()) chips.push({ key: 'dateDebut', label: `Début : ${this.dateDebut()}` });
    if (this.dateFin()) chips.push({ key: 'dateFin', label: `Fin : ${this.dateFin()}` });
    return chips;
  });

  ngOnInit(): void {
    this.reseau.listEquipements({ page: 1, page_size: 200 }).subscribe({
      next: (res) => this.equipements.set(res.items),
      error: () => {},
    });
    this.load();
  }

  typeDirectionLabel(t: TypeDirectionTransport): string {
    return t === 'omvg' ? 'OMVG' : 'Transport HTB';
  }

  canCreate(): boolean {
    return this.auth.hasRole('DISPATCHER', 'ADMIN_DISPATCHING');
  }

  canValidate(): boolean {
    return this.auth.hasRole('ADMIN_DISPATCHING', 'ADMIN_SAQS');
  }

  onTypeDirectionChange(value: string): void {
    this.typeDirection.set(value ? (value as TypeDirectionTransport) : null);
  }

  onEquipementChange(value: string): void {
    this.equipementId.set(value ? Number(value) : null);
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
    this.typeDirection.set(null);
    this.equipementId.set(null);
    this.statut.set(null);
    this.dateDebut.set('');
    this.dateFin.set('');
    this.page.set(1);
    this.load();
  }

  removeFilter(key: FilterChipKey): void {
    switch (key) {
      case 'typeDirection':
        this.typeDirection.set(null);
        break;
      case 'equipement':
        this.equipementId.set(null);
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

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.selectedIds.set(new Set());

    this.service
      .list({
        page: this.page(),
        page_size: this.pageSize(),
        type_direction: this.typeDirection() ?? undefined,
        equipement_transport_id: this.equipementId() ?? undefined,
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
