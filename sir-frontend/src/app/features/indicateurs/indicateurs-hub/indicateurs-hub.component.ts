import { DecimalPipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Region } from '../../../shared/models/geo.models';
import { HistoriquePoint, TableauDeBordResponse, TopFeederItem } from '../../../shared/models/indicateurs.models';
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

  formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('fr-FR', { maximumFractionDigits: 2 });
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
