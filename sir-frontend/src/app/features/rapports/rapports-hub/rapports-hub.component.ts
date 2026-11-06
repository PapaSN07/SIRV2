import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { AuthService } from '../../../core/auth/auth.service';
import {
  ApercuHebdoDD,
  ApercuMensuelDistribution,
  ApercuSerie,
  ApercuValeur,
  RapportDirection,
  RapportFormat,
  RapportStatusResponse,
} from '../../../shared/models/rapports.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { BarreItem, BarresComponent } from '../../../shared/ui/barres/barres.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { ArchivageResponse } from '../../../shared/models/interruption.models';
import { InterruptionDistributionService } from '../../interruptions-distribution/services/interruption-distribution.service';
import { RapportsService } from '../services/rapports.service';

/**
 * Rapports conservés (06/11/2026) : ceux qui ont une mise en forme et des graphiques.
 * Journalier, hebdomadaire simple et mensuel transport (tableaux bruts) sont retirés de l'écran.
 */
type RapportKind = 'hebdo_dd' | 'mensuel_dist' | 'annuel';

const MOIS_NOMS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

@Component({
  selector: 'sir-rapports-hub',
  standalone: true,
  imports: [PageHeaderComponent, AnalyticsNavComponent, BarresComponent, DecimalPipe],
  templateUrl: './rapports-hub.component.html',
  styleUrl: './rapports-hub.component.scss',
})
export class RapportsHubComponent implements OnInit {
  private readonly rapports = inject(RapportsService);
  private readonly auth = inject(AuthService);
  private readonly interruptions = inject(InterruptionDistributionService);

  /** Archivage du mois après le rapport mensuel CRSE (décision SENELEC du 27/10). */
  readonly archivageConfirme = signal(false);
  readonly archivageEnCours = signal(false);
  readonly archivage = signal<ArchivageResponse | null>(null);

  readonly generating = signal(false);
  readonly error = signal<string | null>(null);
  readonly status = signal<RapportStatusResponse | null>(null);

  readonly kind = signal<RapportKind>('mensuel_dist');
  readonly format = signal<RapportFormat>('pdf');
  readonly date = signal(this.todayIso());
  readonly annee = signal(new Date().getFullYear());
  readonly mois = signal(new Date().getMonth() + 1);
  readonly direction = signal<RapportDirection>('distribution');
  readonly regionId = signal<number | null>(null);

  /** Visualisation : chiffres du rapport choisi, affichés avant le téléchargement. */
  readonly apercuHebdo = signal<ApercuHebdoDD | null>(null);
  readonly apercuMensuel = signal<ApercuMensuelDistribution | null>(null);
  readonly apercuLoading = signal(false);
  readonly apercuError = signal<string | null>(null);

  readonly apercuIndicateurs = computed((): ApercuValeur[] =>
    this.kind() === 'hebdo_dd' ? (this.apercuHebdo()?.indicateurs ?? []) : (this.apercuMensuel()?.indicateurs ?? []),
  );
  readonly hebdoCategories = computed(() => this.barresEnd(this.apercuHebdo()?.categories ?? [], true));
  readonly hebdoServices = computed(() => this.barresEnd(this.apercuHebdo()?.services ?? [], true));
  readonly hebdoJours = computed((): BarreItem[] =>
    (this.apercuHebdo()?.jours ?? []).map((j) => ({ libelle: j.libelle, valeur: j.end_mwh, detail: `${j.nombre} interr.` })),
  );
  readonly mensuelServices = computed(() => this.barresEnd(this.apercuMensuel()?.services ?? [], false));
  readonly mensuelFeeders = computed(() => this.barresEnd(this.apercuMensuel()?.top_feeders ?? [], false));
  readonly libelleMois = computed(() => `${MOIS_NOMS[this.mois() - 1] ?? ''} ${this.annee()}`);

  ngOnInit(): void {
    this.setKind(this.canHebdoDD() ? 'hebdo_dd' : 'mensuel_dist');
  }

  /** Changement d'un paramètre (date, mois, année) : l'aperçu suit. */
  onParametre(): void {
    this.status.set(null);
    this.chargerApercu();
  }

  ecart(v: ApercuValeur): number | null {
    if (v.precedent === null || v.precedent === 0) return null;
    return Math.round(((v.valeur - v.precedent) / v.precedent) * 100);
  }

  canDistributionReports(): boolean {
    return this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR', 'ADMIN_SAQS', 'SUPERVISEUR');
  }

  /** Rapport national de la Direction de la Distribution (envoyé chaque samedi à 8 h). */
  canHebdoDD(): boolean {
    return this.auth.hasRole('ADMIN_SCR', 'ADMIN_SAQS', 'SUPERADMIN');
  }

  canConsolide(): boolean {
    return this.auth.hasRole('ADMIN_SAQS');
  }

  canArchiver(): boolean {
    return this.auth.hasRole('ADMIN_SCR', 'ADMIN_SAQS', 'SUPERADMIN');
  }

  archiverMois(): void {
    if (!this.archivageConfirme()) {
      this.archivageConfirme.set(true);
      return;
    }
    this.archivageEnCours.set(true);
    this.error.set(null);
    this.interruptions.archiverMois({ annee: this.annee(), mois: this.mois() }).subscribe({
      next: (res) => {
        this.archivage.set(res);
        this.archivageEnCours.set(false);
        this.archivageConfirme.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.archivageEnCours.set(false);
        this.archivageConfirme.set(false);
      },
    });
  }

  setKind(value: RapportKind): void {
    this.archivageConfirme.set(false);
    this.archivage.set(null);
    this.kind.set(value);
    if (value === 'hebdo_dd') {
      this.format.set('docx');
      this.date.set(this.dernierVendrediIso());
    } else if (this.format() === 'docx') {
      this.format.set('pdf');
    }
    this.status.set(null);
    this.error.set(null);
    this.chargerApercu();
  }

  private chargerApercu(): void {
    this.apercuError.set(null);
    const kind = this.kind();
    if (kind === 'annuel') return;
    this.apercuLoading.set(true);
    const fin = () => this.apercuLoading.set(false);
    const echec = (err: Error) => {
      this.apercuError.set(err.message);
      fin();
    };
    if (kind === 'hebdo_dd') {
      this.rapports.getApercuHebdoDD(this.date()).subscribe({
        next: (a) => {
          this.apercuHebdo.set(a);
          fin();
        },
        error: echec,
      });
    } else {
      this.rapports.getApercuMensuelDistribution(this.annee(), this.mois(), this.regionId()).subscribe({
        next: (a) => {
          this.apercuMensuel.set(a);
          fin();
        },
        error: echec,
      });
    }
  }

  private barresEnd(series: ApercuSerie[], comparer: boolean): BarreItem[] {
    return series
      .filter((s) => s.end_mwh > 0 || s.nombre > 0 || (comparer && (s.end_mwh_precedent ?? 0) > 0))
      .map((s) => ({
        libelle: s.libelle,
        valeur: s.end_mwh,
        comparaison: comparer ? s.end_mwh_precedent : undefined,
        detail: s.part_pct !== null ? `${s.part_pct.toLocaleString('fr-FR')} %` : `${s.nombre} interr.`,
      }));
  }

  generate(): void {
    this.generating.set(true);
    this.error.set(null);
    this.status.set(null);

    const onEnqueue = (taskId: string) => {
      this.rapports.pollStatus(taskId).subscribe({
        next: (s) => this.status.set(s),
        error: (err: Error) => {
          this.error.set(err.message);
          this.generating.set(false);
        },
        complete: () => this.generating.set(false),
      });
    };

    const fmt = this.format();

    switch (this.kind()) {
      case 'hebdo_dd':
        this.rapports.enqueueHebdoDD({ date_fin: this.date(), format: fmt }).subscribe({
          next: (r) => onEnqueue(r.task_id),
          error: (err: Error) => {
            this.error.set(err.message);
            this.generating.set(false);
          },
        });
        break;
      case 'mensuel_dist':
        this.rapports
          .enqueueMensuelDistribution({
            annee: this.annee(),
            mois: this.mois(),
            region_id: this.regionId() ?? undefined,
            format: fmt,
          })
          .subscribe({
            next: (r) => onEnqueue(r.task_id),
            error: (err: Error) => {
              this.error.set(err.message);
              this.generating.set(false);
            },
          });
        break;
      case 'annuel':
        this.rapports
          .enqueueAnnuel({
            annee: this.annee(),
            direction: 'distribution',
            region_id: this.regionId() ?? undefined,
            format: fmt,
          })
          .subscribe({
            next: (r) => onEnqueue(r.task_id),
            error: (err: Error) => {
              this.error.set(err.message);
              this.generating.set(false);
            },
          });
        break;
    }
  }

  download(): void {
    const s = this.status();
    if (!s || s.statut !== 'success') return;
    this.rapports.download(s.task_id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = s.file_name ?? `rapport-${s.task_id}.${s.format}`;
        a.click();
        URL.revokeObjectURL(url);
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }

  statutLabel(statut: string): string {
    switch (statut) {
      case 'pending':
        return 'En attente';
      case 'started':
        return 'Génération en cours';
      case 'success':
        return 'Prêt au téléchargement';
      case 'failure':
        return 'Échec';
      default:
        return statut;
    }
  }

  /** Vendredi de la dernière semaine complète (samedi → vendredi). */
  private dernierVendrediIso(): string {
    const d = new Date();
    const recul = (d.getDay() - 5 + 7) % 7 || 7;
    d.setDate(d.getDate() - recul);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }

  private todayIso(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
}
