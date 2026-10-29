import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, effect, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { AuthService } from '../../core/auth/auth.service';
import { NotificationService } from '../../core/notifications/notification.service';
import { notificationEventLabel } from '../../core/notifications/notification.utils';
import {
  CauseRepartitionItem,
  HistoriquePoint,
  IndicateurSuivi,
  NatureServiceRepartition,
  ObjectifsPilotageUpdate,
  PilotageResponse,
  PosteOuvertCarte,
  TableauDeBordResponse,
  TendanceResponse,
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
  saidi: number;
  saifi: number;
  saidiHeight: number;
  saifiHeight: number;
}

type DashboardTab = 'synthese' | 'objectifs' | 'reseau';

/**
 * Cadre du fond de carte assets/maps/senegal.svg (Natural Earth 1:10m, domaine public) :
 * toute position est exprimée en % de ce cadre, pour les postes comme pour les repères.
 */
const MAP_FRAME = { lonMin: -17.55, lonMax: -11.3, latMin: 12.25, latMax: 16.75 };

function projectSenegal(lon: number, lat: number): { left: number; top: number } {
  return {
    left: ((lon - MAP_FRAME.lonMin) / (MAP_FRAME.lonMax - MAP_FRAME.lonMin)) * 100,
    top: ((MAP_FRAME.latMax - lat) / (MAP_FRAME.latMax - MAP_FRAME.latMin)) * 100,
  };
}

const MAP_CITIES: { name: string; lon: number; lat: number; side?: 'right' }[] = [
  // Dakar est au bord ouest du cadre : étiquette à droite du point
  { name: 'Dakar', lon: -17.45, lat: 14.69, side: 'right' },
  { name: 'Thiès', lon: -16.93, lat: 14.79 },
  { name: 'Saint-Louis', lon: -16.49, lat: 16.03 },
  { name: 'Touba', lon: -15.88, lat: 14.86 },
  { name: 'Kaolack', lon: -16.07, lat: 14.15 },
  { name: 'Ziguinchor', lon: -16.27, lat: 12.57 },
  { name: 'Tambacounda', lon: -13.67, lat: 13.77 },
  { name: 'Matam', lon: -13.25, lat: 15.66 },
];

interface ObjectifDraft {
  end_mwh: string;
  saifi: string;
  saidi: string;
  defauts_100km: string;
}

interface MapPin extends PosteOuvertCarte {
  left: number;
  top: number;
}

interface ServiceBar {
  service_id: number;
  code: string;
  libelle: string;
  endHeight: number;
  nombreHeight: number;
  end_kwh: number;
  nombre: number;
}

const MONTH_LABELS = ['JAN', 'FÉV', 'MAR', 'AVR', 'MAI', 'JUN', 'JUL', 'AOÛ', 'SEP', 'OCT', 'NOV', 'DÉC'];

const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

/** Première année proposée dans le sélecteur de période (historique SIR v1 migré). */
const PREMIERE_ANNEE = 2010;

const CAUSE_COLORS = ['#5b2c6f', '#7a4b8c', '#9a74aa', '#b79ac4', '#d4c4dc'];

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
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly tabs: { id: DashboardTab; label: string; icon: string }[] = [
    { id: 'synthese', label: 'Synthèse', icon: 'monitoring' },
    { id: 'objectifs', label: 'Objectifs', icon: 'flag' },
    { id: 'reseau', label: 'Réseau', icon: 'hub' },
  ];
  /** Vue courante, conservée dans l'URL (?vue=) pour le retour arrière et les liens. */
  readonly tab = signal<DashboardTab>(this.initialTab());

  private initialTab(): DashboardTab {
    const vue = this.route.snapshot.queryParamMap.get('vue');
    return vue === 'objectifs' || vue === 'reseau' ? vue : 'synthese';
  }

  selectTab(tab: DashboardTab): void {
    this.tab.set(tab);
    void this.router.navigate([], {
      relativeTo: this.route,
      replaceUrl: true,
      queryParams: { vue: tab === 'synthese' ? null : tab },
      queryParamsHandling: 'merge',
    });
  }
  private readonly notifications = inject(NotificationService);

  readonly toastMessage = signal<string | null>(null);
  private seenNotificationIds = new Set<string>();

  readonly loading = signal(true);
  readonly loadError = signal<string | null>(null);
  readonly chartReady = signal(false);
  readonly kpi = signal<TableauDeBordResponse | null>(null);
  readonly distributionStats = signal<InterruptionDistributionStats | null>(null);
  readonly chartMonths = signal<ChartMonth[]>([]);
  readonly saidiMax = computed(() => Math.max(0, ...this.chartMonths().map((m) => m.saidi)));
  readonly saifiMax = computed(() => Math.max(0, ...this.chartMonths().map((m) => m.saifi)));
  readonly recentInterruptions = signal<InterruptionDistribution[]>([]);
  readonly interruptionsLoading = signal(true);
  readonly interruptionsError = signal<string | null>(null);

  readonly periode = signal(this.currentPeriode());

  readonly periodeAnnee = computed(() => Number(this.periode().slice(0, 4)));
  readonly periodeMois = computed(() => Number(this.periode().slice(5, 7)));

  /** Années proposées : de l'année en cours jusqu'au début de l'historique. */
  readonly anneeOptions = computed(() => {
    const courante = new Date().getFullYear();
    return Array.from({ length: courante - PREMIERE_ANNEE + 1 }, (_, i) => courante - i);
  });

  /** Mois de l'année choisie ; les mois futurs ne sont pas proposés. */
  readonly moisOptions = computed(() => {
    const now = new Date();
    const dernier = this.periodeAnnee() === now.getFullYear() ? now.getMonth() + 1 : 12;
    return MONTH_NAMES.slice(0, dernier).map((label, i) => ({ value: i + 1, label }));
  });

  readonly isPeriodeCourante = computed(() => this.periode() === this.currentPeriode());

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

  readonly pilotage = signal<PilotageResponse | null>(null);
  readonly pilotageLoading = signal(false);
  readonly pilotageError = signal<string | null>(null);
  readonly objectifDraft = signal<ObjectifDraft>({
    end_mwh: '',
    saifi: '',
    saidi: '',
    defauts_100km: '',
  });
  readonly objectifSaving = signal(false);
  readonly objectifMessage = signal<string | null>(null);
  readonly tendanceCible = signal<'feeder' | 'poste'>('feeder');
  readonly tendanceAnnees = signal(3);
  readonly tendance = signal<TendanceResponse | null>(null);
  readonly tendanceLoading = signal(false);
  readonly tendanceError = signal<string | null>(null);
  private tendanceChoice: { cible: 'feeder' | 'poste'; id: number } | null = null;

  readonly natureService = computed((): NatureServiceRepartition | null => this.kpi()?.nature_service ?? null);

  readonly mapPins = computed((): MapPin[] =>
    (this.pilotage()?.postes_ouverts ?? [])
      .filter((poste) => poste.latitude !== null && poste.longitude !== null)
      .map((poste) => {
        const { left, top } = projectSenegal(poste.longitude!, poste.latitude!);
        return { ...poste, left: Math.min(97, Math.max(3, left)), top: Math.min(97, Math.max(3, top)) };
      }),
  );

  /** Repères sur le fond de carte (même projection que les postes). */
  readonly mapCities = MAP_CITIES.map((c) => ({ ...c, ...projectSenegal(c.lon, c.lat) }));

  readonly postesSansCoord = computed(() =>
    (this.pilotage()?.postes_ouverts ?? []).filter(
      (poste) => poste.latitude === null || poste.longitude === null,
    ),
  );

  readonly serviceBars = computed((): ServiceBar[] => {
    const services = this.natureService()?.services ?? [];
    const maxEnd = Math.max(...services.map((service) => service.end_kwh), 1);
    const maxNombre = Math.max(...services.map((service) => service.nombre), 1);
    return services.map((service) => ({
      service_id: service.service_id,
      code: service.code,
      libelle: service.libelle,
      end_kwh: service.end_kwh,
      nombre: service.nombre,
      endHeight: Math.round((service.end_kwh / maxEnd) * 100),
      nombreHeight: Math.round((service.nombre / maxNombre) * 100),
    }));
  });

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
    this.loadPilotage();
    this.loadRecentInterruptions();
  }

  onPeriodeChange(value: string): void {
    if (value === this.periode()) return;
    this.periode.set(value);
    this.loadDashboard();
    this.loadPilotage();
  }

  onAnneeChange(valeur: string): void {
    const annee = Number(valeur);
    const now = new Date();
    // Année en cours : on ne dépasse pas le mois actuel
    const mois = annee === now.getFullYear() ? Math.min(this.periodeMois(), now.getMonth() + 1) : this.periodeMois();
    this.onPeriodeChange(`${annee}-${String(mois).padStart(2, '0')}`);
  }

  onMoisChange(valeur: string): void {
    this.onPeriodeChange(`${this.periodeAnnee()}-${valeur.padStart(2, '0')}`);
  }

  /** Décale la période d'un mois (−1 = précédent, +1 = suivant), bornée à l'historique et au mois courant. */
  decalerPeriode(delta: -1 | 1): void {
    const d = new Date(this.periodeAnnee(), this.periodeMois() - 1 + delta, 1);
    const now = new Date();
    if (d.getFullYear() < PREMIERE_ANNEE || d > now) return;
    this.onPeriodeChange(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`);
  }

  peutReculer(): boolean {
    return !(this.periodeAnnee() === PREMIERE_ANNEE && this.periodeMois() === 1);
  }

  canCreateInterruption(): boolean {
    return this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR');
  }

  isBrcUser(): boolean {
    return this.auth.isExactRole('BRC');
  }

  formatNumber(value: number | null | undefined, digits = 1): string {
    if (value === null || value === undefined) return '—';
    return value.toLocaleString('fr-FR', { maximumFractionDigits: digits });
  }

  /** SAIFI : 2 décimales ; SAIDI en heures : 3 décimales ; END et autres : 1 décimale. */
  formatIndicateur(value: number | null | undefined, code: string): string {
    const c = code.toUpperCase();
    return this.formatNumber(value, c === 'SAIFI' ? 2 : c === 'SAIDI' ? 3 : 1);
  }

  formatTaux(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    return `${value.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`;
  }

  gaugePct(value: number | null | undefined): number {
    if (value === null || value === undefined) return 0;
    return Math.max(0, Math.min(100, value));
  }

  /** Libellé lisible de la jauge (la couleur seule ne suffit pas). */
  gaugeStatus(value: number | null | undefined): { tone: string; label: string } {
    if (value === null || value === undefined) return { tone: 'empty', label: 'Pas d’objectif' };
    if (value <= 90) return { tone: 'ok', label: 'Dans l’objectif' };
    if (value <= 100) return { tone: 'warn', label: 'À surveiller' };
    return { tone: 'over', label: 'Objectif dépassé' };
  }

  gaugeClass(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'gauge gauge--empty';
    if (value <= 90) return 'gauge gauge--ok';
    if (value <= 100) return 'gauge gauge--warn';
    return 'gauge gauge--over';
  }

  onObjectifInput(field: keyof ObjectifDraft, value: string): void {
    this.objectifDraft.update((draft) => ({ ...draft, [field]: value }));
  }

  saveObjectifs(): void {
    const data = this.pilotage();
    if (!data) return;
    const draft = this.objectifDraft();
    const body: ObjectifsPilotageUpdate = { annee: data.annee_objectif };
    const end = this.parseObjectif(draft.end_mwh);
    const saifi = this.parseObjectif(draft.saifi);
    const saidi = this.parseObjectif(draft.saidi);
    const defauts = this.parseObjectif(draft.defauts_100km);
    if (end === null || saifi === null || saidi === null || defauts === null) {
      this.objectifMessage.set('Chaque objectif saisi doit être un nombre positif ou nul.');
      return;
    }
    if (end !== undefined) body.end_mwh = end;
    if (saifi !== undefined) body.saifi = saifi;
    if (saidi !== undefined) body.saidi = saidi;
    if (defauts !== undefined) body.defauts_100km = defauts;
    if (
      body.end_mwh === undefined &&
      body.saifi === undefined &&
      body.saidi === undefined &&
      body.defauts_100km === undefined
    ) {
      this.objectifMessage.set('Saisissez au moins un objectif annuel.');
      return;
    }
    this.objectifSaving.set(true);
    this.objectifMessage.set(null);
    this.dashboardService.saveObjectifs(body).subscribe({
      next: () => {
        this.objectifSaving.set(false);
        this.objectifMessage.set('Objectifs enregistrés.');
        this.loadPilotage();
      },
      error: (err: Error) => {
        this.objectifSaving.set(false);
        this.objectifMessage.set(err.message);
      },
    });
  }

  onTendanceCibleChange(value: string): void {
    const cible = value === 'poste' ? 'poste' : 'feeder';
    this.tendanceCible.set(cible);
    const data = this.pilotage();
    if (!data) return;
    const id = cible === 'poste' ? data.top_postes[0]?.poste_id : data.top_feeders[0]?.feeder_id;
    if (id) this.selectTendance(cible, id);
  }

  onTendanceIdChange(value: string): void {
    const id = Number(value);
    if (id > 0) this.selectTendance(this.tendanceCible(), id);
  }

  onTendanceAnneesChange(value: string): void {
    const annees = Number(value) === 2 ? 2 : 3;
    this.tendanceAnnees.set(annees);
    if (this.tendanceChoice) {
      this.loadTendance(this.tendanceChoice.cible, this.tendanceChoice.id);
    }
  }

  tendanceId(): string {
    const id = this.tendanceChoice?.id ?? this.tendance()?.cible_id;
    return id ? String(id) : '';
  }

  trendChart(): { historique: string; courbe: string } | null {
    const data = this.tendance();
    if (!data?.points.length) return null;
    const nombres = data.points.map((point) => point.nombre);
    const courbe = [
      ...data.points.map((point) => point.tendance_nombre),
      ...data.previsions.map((point) => point.tendance_nombre),
    ];
    const max = Math.max(...nombres, ...courbe, 1);
    const total = courbe.length;
    const draw = (series: number[], start: number) =>
      series
        .map((value, index) => {
          const x = 16 + ((start + index) / Math.max(total - 1, 1)) * 608;
          const y = 8 + (1 - value / max) * 132;
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        })
        .join(' ');
    return { historique: draw(nombres, 0), courbe: draw(courbe, 0) };
  }

  formatEndKwh(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    return Math.round(value).toLocaleString('fr-FR');
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
      // Le toast est un signal : écriture autorisée explicitement (sinon NG0600, toast jamais affiché)
    }, { allowSignalWrites: true });
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
      saidi: this.dashboardService.getHistorique('saidi', 1, undefined, this.periode()).pipe(
        catchError(() => of({ points: [] as HistoriquePoint[] })),
      ),
      saifi: this.dashboardService.getHistorique('saifi', 1, undefined, this.periode()).pipe(
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

  private loadPilotage(): void {
    this.pilotageLoading.set(true);
    this.pilotageError.set(null);
    this.dashboardService.getPilotage({ periode: this.periode() }).subscribe({
      next: (data) => {
        this.pilotage.set(data);
        this.pilotageLoading.set(false);
        this.syncObjectifDraft(data);
        this.ensureTendance(data);
      },
      error: (err: Error) => {
        this.pilotageError.set(err.message);
        this.pilotageLoading.set(false);
      },
    });
  }

  private syncObjectifDraft(data: PilotageResponse): void {
    const byCode = new Map(data.indicateurs.map((item) => [item.code, item]));
    this.objectifDraft.set({
      end_mwh: this.draftValue(byCode.get('END')),
      saifi: this.draftValue(byCode.get('SAIFI')),
      saidi: this.draftValue(byCode.get('SAIDI')),
      defauts_100km: this.draftValue(byCode.get('DEFAUTS_100KM')),
    });
  }

  private draftValue(item: IndicateurSuivi | undefined): string {
    if (!item || item.objectif_annuel === null || item.objectif_annuel === undefined) return '';
    return String(item.objectif_annuel);
  }

  private parseObjectif(value: string): number | null | undefined {
    const trimmed = value.trim();
    if (!trimmed) return undefined;
    const parsed = Number(trimmed.replace(',', '.'));
    if (!Number.isFinite(parsed) || parsed < 0) return null;
    return parsed;
  }

  private ensureTendance(data: PilotageResponse): void {
    if (this.tendanceChoice) {
      this.loadTendance(this.tendanceChoice.cible, this.tendanceChoice.id);
      return;
    }
    const feeder = data.top_feeders[0];
    if (!feeder) return;
    this.selectTendance('feeder', feeder.feeder_id);
  }

  private selectTendance(cible: 'feeder' | 'poste', id: number): void {
    this.tendanceCible.set(cible);
    this.tendanceChoice = { cible, id };
    this.loadTendance(cible, id);
  }

  private loadTendance(cible: 'feeder' | 'poste', id: number): void {
    this.tendanceLoading.set(true);
    this.tendanceError.set(null);
    this.dashboardService.getTendance(cible, id, this.tendanceAnnees()).subscribe({
      next: (data) => {
        this.tendance.set(data);
        this.tendanceLoading.set(false);
      },
      error: (err: Error) => {
        this.tendanceError.set(err.message);
        this.tendanceLoading.set(false);
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
            const [annee, mois] = key.split('-').map(Number);
            const nom = MONTH_LABELS[mois - 1] ?? String(mois);
            return {
              key,
              // Janvier porte l'année : repère quand la courbe chevauche deux années
              label: mois === 1 ? `${nom} ${String(annee).slice(2)}` : nom,
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

    // Une échelle par indicateur : SAIDI en heures, SAIFI en interruptions par client
    const maxSaidi = Math.max(...months.map((m) => m.saidi), 0) || 1;
    const maxSaifi = Math.max(...months.map((m) => m.saifi), 0) || 1;

    return months.map((month) => ({
      key: month.key,
      label: month.label,
      saidi: month.saidi,
      saifi: month.saifi,
      saidiHeight: Math.round((month.saidi / maxSaidi) * 100),
      saifiHeight: Math.round((month.saifi / maxSaifi) * 100),
    }));
  }

  readonly currentPeriodeValue = this.currentPeriode();

  private currentPeriode(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  }
}
