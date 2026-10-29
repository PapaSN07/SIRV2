import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Region } from '../../../shared/models/geo.models';
import { CauseRepartitionItem, HistoriquePoint, NatureRepartitionItem, TableauDeBordResponse, TopFeederItem } from '../../../shared/models/indicateurs.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { GeoService } from '../../geo/services/geo.service';
import { IndicateursService } from '../services/indicateurs.service';

interface ChartMonth {
  key: string;
  label: string;
  height: number;
}

const MONTH_LABELS = ['JAN', 'FÉV', 'MAR', 'AVR', 'MAI', 'JUN', 'JUL', 'AOÛ', 'SEP', 'OCT', 'NOV', 'DÉC'];
const CAUSE_COLORS = ['#5b2c6f', '#7a4b8c', '#9a74aa', '#b79ac4', '#d4c4dc'];

@Component({
  selector: 'sir-indicateurs-hub',
  standalone: true,
  imports: [DecimalPipe, PageHeaderComponent, AnalyticsNavComponent],
  templateUrl: './indicateurs-hub.component.html',
  styleUrl: './indicateurs-hub.component.scss',
})
export class IndicateursHubComponent implements OnInit {
  private readonly indicateurs = inject(IndicateursService);
  private readonly geo = inject(GeoService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly kpi = signal<TableauDeBordResponse | null>(null);
  readonly topFeeders = signal<TopFeederItem[]>([]);
  readonly endChart = signal<ChartMonth[]>([]);
  readonly chartReady = signal(false);

  readonly regions = signal<Region[]>([]);
  readonly regionId = signal<number | null>(null);
  readonly periode = signal(this.currentPeriode());

  readonly periodeOptions = computed(() => {
    const options: { value: string; label: string }[] = [];
    const now = new Date();
    for (let i = 0; i < 12; i += 1) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      options.push({ value, label: `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}` });
    }
    return options;
  });

  readonly causesRepartition = computed((): CauseRepartitionItem[] => this.kpi()?.causes_repartition ?? []);

  readonly naturesRepartition = computed((): NatureRepartitionItem[] => this.kpi()?.natures_repartition ?? []);

  readonly causeDonutStyle = computed((): string => {
    const items = this.causesRepartition();
    if (!items.length) {
      return 'conic-gradient(#e5e7eb 0deg 360deg)';
    }
    let cursor = 0;
    const stops: string[] = [];
    items.forEach((item, index) => {
      const span = (item.percent / 100) * 360;
      const color = CAUSE_COLORS[index % CAUSE_COLORS.length];
      stops.push(`${color} ${cursor}deg ${cursor + span}deg`);
      cursor += span;
    });
    return `conic-gradient(${stops.join(', ')})`;
  });

  readonly causeDonutTotal = computed((): number => {
    const kpi = this.kpi();
    if (!kpi) return 0;
    const fromCauses = this.causesRepartition().reduce((sum, item) => sum + item.nombre, 0);
    return fromCauses || kpi.nb_interruptions_mois || 0;
  });

  causeColor(index: number): string {
    return CAUSE_COLORS[index % CAUSE_COLORS.length];
  }

  ngOnInit(): void {
    this.geo.getRegions().subscribe({
      next: (r) => this.regions.set(r),
      error: () => {},
    });
    this.load();
  }

  onRegionChange(value: string): void {
    this.regionId.set(value ? Number(value) : null);
    this.load();
  }

  onPeriodeChange(value: string): void {
    this.periode.set(value);
    this.load();
  }

  formatNumber(value: number | null | undefined, digits = 2): string {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('fr-FR', { maximumFractionDigits: digits });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const params = {
      periode: this.periode(),
      region_id: this.regionId() ?? undefined,
    };

    forkJoin({
      kpi: this.indicateurs.getTableauDeBord(params).pipe(catchError((e: Error) => {
        this.error.set(e.message);
        return of(null);
      })),
      endHist: this.indicateurs.getHistorique('end', 2, this.regionId() ?? undefined).pipe(
        catchError(() => of({ points: [] as HistoriquePoint[] })),
      ),
      top: this.indicateurs.getTopFeeders({ ...params, limit: 10 }).pipe(
        catchError(() => of({ items: [] as TopFeederItem[] })),
      ),
    }).subscribe({
      next: ({ kpi, endHist, top }) => {
        if (kpi) this.kpi.set(kpi);
        this.topFeeders.set(top.items ?? []);
        this.endChart.set(this.buildEndChart(endHist.points));
        this.loading.set(false);
        requestAnimationFrame(() => this.chartReady.set(true));
      },
      error: () => this.loading.set(false),
    });
  }

  private currentPeriode(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }

  private buildEndChart(points: HistoriquePoint[]): ChartMonth[] {
    const sorted = [...points].sort((a, b) =>
      a.annee !== b.annee ? a.annee - b.annee : a.mois - b.mois,
    );
    const slice = sorted.slice(-12);
    const max = Math.max(...slice.map((p) => p.valeur), 1);
    return slice.map((p) => ({
      key: `${p.annee}-${p.mois}`,
      label: MONTH_LABELS[p.mois - 1] ?? String(p.mois),
      height: Math.round((p.valeur / max) * 100),
    }));
  }
}
