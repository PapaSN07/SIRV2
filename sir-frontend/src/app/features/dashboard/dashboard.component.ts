import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { AuthService } from '../../core/auth/auth.service';
import { NotificationService } from '../../core/notifications/notification.service';
import { notificationEventLabel } from '../../core/notifications/notification.utils';
import {
  CauseRepartitionItem,
  HistoriquePoint,
  TableauDeBordResponse,
} from '../../shared/models/indicateurs.models';
import {
  InterruptionDistribution,
  InterruptionDistributionStats,
} from '../../shared/models/interruption.models';
import { statutLabel } from '../../shared/utils/statut.utils';
import { InterruptionDistributionService } from '../interruptions-distribution/services/interruption-distribution.service';
import { IndicateursService } from '../indicateurs/services/indicateurs.service';

interface ChartMonth {
  key: string;
  label: string;
  saidiHeight: number;
  saifiHeight: number;
}

const MONTH_LABELS = ['JAN', 'FÉV', 'MAR', 'AVR', 'MAI', 'JUN', 'JUL', 'AOÛ', 'SEP', 'OCT', 'NOV', 'DÉC'];

const CAUSE_COLORS = ['#3c1053', '#ad1457', '#f4811f', '#c62828', '#5a1a72'];

@Component({
  selector: 'sir-dashboard',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly dashboardService = inject(IndicateursService);
  private readonly interruptionService = inject(InterruptionDistributionService);
  private readonly auth = inject(AuthService);
  private readonly notifications = inject(NotificationService);

  readonly toastMessage = signal<string | null>(null);
  private seenNotificationIds = new Set<string>();

  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly chartReady = signal(false);
  readonly kpi = signal<TableauDeBordResponse | null>(null);
  readonly distributionStats = signal<InterruptionDistributionStats | null>(null);
  readonly chartMonths = signal<ChartMonth[]>([]);
  readonly recentInterruptions = signal<InterruptionDistribution[]>([]);
  readonly interruptionsLoading = signal(true);
  readonly interruptionsError = signal<string | null>(null);

  readonly periode = signal(this.currentPeriode());

  readonly periodeOptions = computed(() => {
    const options: { value: string; label: string }[] = [];
    const now = new Date();
    for (let i = 0; i < 6; i += 1) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      options.push({ value, label: `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}` });
    }
    return options;
  });

  /** Répartition par cause — données API tableau de bord. */
  readonly causeRepartition = computed((): CauseRepartitionItem[] => {
    const rows = this.kpi()?.causes_repartition ?? [];
    return rows.map((item, index) => ({
      ...item,
      color: CAUSE_COLORS[index % CAUSE_COLORS.length],
    }));
  });

  readonly causeTotal = computed(() => this.kpi()?.nb_interruptions_mois ?? 0);

  readonly scopeSubtitle = computed(() => {
    const data = this.kpi();
    if (!data) return '';
    switch (data.niveau) {
      case 'region':
        return 'Périmètre régional — tous les services de votre région';
      case 'service':
        return 'Périmètre service — votre centre de conduite';
      case 'delegation':
        return 'Périmètre délégation';
      case 'national':
        return 'Vue nationale';
      default:
        return '';
    }
  });

  readonly hasCauseData = computed(() => (this.kpi()?.causes_repartition?.length ?? 0) > 0);

  readonly activeProgress = computed(() => {
    const data = this.kpi();
    if (!data || data.nb_interruptions_mois === 0) return 0;
    return Math.min(100, Math.round((data.nb_interruptions_actives / data.nb_interruptions_mois) * 100));
  });

  readonly periodLabel = computed(() => {
    const data = this.kpi();
    if (!data) return '—';
    return `${String(data.mois).padStart(2, '0')}/${data.annee}`;
  });

  ngOnInit(): void {
    this.loadDashboard();
    this.loadRecentInterruptions();
  }

  onPeriodeChange(value: string): void {
    this.periode.set(value);
    this.loadDashboard();
  }

  canCreateInterruption(): boolean {
    return this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR');
  }

  isBrcUser(): boolean {
    return this.auth.hasRole('BRC');
  }

  formatNumber(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('fr-FR', { maximumFractionDigits: 1 });
  }

  readonly statutLabel = statutLabel;

  constructor() {
    effect(() => {
      const items = this.notifications.items();
      for (const item of items) {
        if (this.seenNotificationIds.has(item.id)) continue;
        this.seenNotificationIds.add(item.id);
        if (item.event_type === 'interruption_creee' || item.event_type === 'rapport_pret') {
          this.toastMessage.set(notificationEventLabel(item.event_type) + ' — ' + item.message);
          setTimeout(() => this.toastMessage.set(null), 8000);
        }
      }
    });
  }

  dismissToast(): void {
    this.toastMessage.set(null);
  }

  causeGradient(): string {
    const items = this.causeRepartition();
    if (!items.length) {
      return 'conic-gradient(#e0e0e0 0% 100%)';
    }
    let cursor = 0;
    const stops = items.map((item) => {
      const start = cursor;
      cursor += item.percent;
      return `${item.color} ${start}% ${cursor}%`;
    });
    return `conic-gradient(${stops.join(', ')})`;
  }

  private loadDashboard(): void {
    this.loading.set(true);
    this.loadError.set(null);

    forkJoin({
      kpi: this.dashboardService.getTableauDeBord({ periode: this.periode() }).pipe(
        catchError((err: Error) => {
          this.loadError.set(err.message);
          return of(null);
        }),
      ),
      stats: this.interruptionService.stats().pipe(catchError(() => of(null))),
      saidi: this.dashboardService.getHistorique('saidi', 1).pipe(
        catchError(() => of({ points: [] as HistoriquePoint[] })),
      ),
      saifi: this.dashboardService.getHistorique('saifi', 1).pipe(
        catchError(() => of({ points: [] as HistoriquePoint[] })),
      ),
    }).subscribe({
      next: ({ kpi, stats, saidi, saifi }) => {
        if (kpi) {
          this.kpi.set(kpi);
        }
        this.distributionStats.set(stats);
        this.chartMonths.set(this.buildChartMonths(saidi.points, saifi.points));
        this.loading.set(false);
        requestAnimationFrame(() => this.chartReady.set(true));
      },
      error: () => {
        this.loading.set(false);
        requestAnimationFrame(() => this.chartReady.set(true));
      },
    });
  }

  private loadRecentInterruptions(): void {
    this.interruptionsLoading.set(true);
    this.interruptionsError.set(null);

    this.interruptionService.list({ page: 1, page_size: 4 }).subscribe({
      next: (res) => {
        this.recentInterruptions.set(res.items);
        this.interruptionsLoading.set(false);
      },
      error: (err: Error) => {
        this.interruptionsError.set(err.message);
        this.interruptionsLoading.set(false);
      },
    });
  }

  private buildChartMonths(saidiPoints: HistoriquePoint[], saifiPoints: HistoriquePoint[]): ChartMonth[] {
    const saidiMap = new Map(saidiPoints.map((p) => [`${p.annee}-${p.mois}`, p.valeur]));
    const saifiMap = new Map(saifiPoints.map((p) => [`${p.annee}-${p.mois}`, p.valeur]));

    const keys = new Set([...saidiMap.keys(), ...saifiMap.keys()]);
    const sortedKeys = [...keys].sort((a, b) => {
      const [ay, am] = a.split('-').map(Number);
      const [by, bm] = b.split('-').map(Number);
      return ay !== by ? ay - by : am - bm;
    });

    const months =
      sortedKeys.length > 0
        ? sortedKeys.slice(-12).map((key) => {
            const [, mois] = key.split('-').map(Number);
            return {
              key,
              label: MONTH_LABELS[mois - 1] ?? String(mois),
              saidi: saidiMap.get(key) ?? 0,
              saifi: saifiMap.get(key) ?? 0,
            };
          })
        : MONTH_LABELS.map((label, index) => ({
            key: `placeholder-${index}`,
            label,
            saidi: 0,
            saifi: 0,
          }));

    const maxValue = Math.max(...months.flatMap((m) => [m.saidi, m.saifi]), 1);

    return months.map((month) => ({
      key: month.key,
      label: month.label,
      saidiHeight: Math.round((month.saidi / maxValue) * 100),
      saifiHeight: Math.round((month.saifi / maxValue) * 100),
    }));
  }

  private currentPeriode(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
}
