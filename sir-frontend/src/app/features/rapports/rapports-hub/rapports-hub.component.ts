import { Component, OnInit, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import {
  RapportDirection,
  RapportFormat,
  RapportStatusResponse,
} from '../../../shared/models/rapports.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { ArchivageResponse } from '../../../shared/models/interruption.models';
import { InterruptionDistributionService } from '../../interruptions-distribution/services/interruption-distribution.service';
import { RapportsService } from '../services/rapports.service';

type RapportKind = 'journalier' | 'mensuel_dist' | 'mensuel_trans' | 'annuel';

@Component({
  selector: 'sir-rapports-hub',
  standalone: true,
  imports: [PageHeaderComponent, AnalyticsNavComponent],
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

  readonly kind = signal<RapportKind>('journalier');
  readonly format = signal<RapportFormat>('pdf');
  readonly date = signal(this.todayIso());
  readonly annee = signal(new Date().getFullYear());
  readonly mois = signal(new Date().getMonth() + 1);
  readonly direction = signal<RapportDirection>('distribution');
  readonly regionId = signal<number | null>(null);

  ngOnInit(): void {}

  canTransportReports(): boolean {
    return this.auth.hasRole('DISPATCHER', 'ADMIN_DISPATCHING', 'ADMIN_SAQS');
  }

  canDistributionReports(): boolean {
    return this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR', 'ADMIN_SAQS', 'SUPERVISEUR');
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
    this.status.set(null);
    this.error.set(null);
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
      case 'journalier':
        this.rapports
          .enqueueJournalier({
            date: this.date(),
            region_id: this.regionId(),
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
      case 'mensuel_trans':
        this.rapports
          .enqueueMensuelTransport({ annee: this.annee(), mois: this.mois(), format: fmt })
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
            direction: this.direction(),
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

  private todayIso(): string {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
}
