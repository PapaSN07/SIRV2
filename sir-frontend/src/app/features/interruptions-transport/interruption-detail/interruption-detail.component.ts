import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { AuthService } from '../../../core/auth/auth.service';
import { HasRoleDirective } from '../../../core/auth/has-role.directive';
import { InterruptionTransportDetail } from '../../../shared/models/interruption-transport.models';
import { ActionStatut, StatutHistorique } from '../../../shared/models/interruption.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { InterruptionTransportService } from '../services/interruption-transport.service';

@Component({
  selector: 'sir-interruption-transport-detail',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    NgTemplateOutlet,
    HasRoleDirective,
    PageHeaderComponent,
    StatusChipComponent,
    InterruptionsNavComponent,
  ],
  templateUrl: './interruption-detail.component.html',
  styleUrl: './interruption-detail.component.scss',
})
export class InterruptionTransportDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(InterruptionTransportService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  readonly timelineSteps = [
    { key: 'en_cours', label: 'En cours' },
    { key: 'cloture', label: 'Clôturée' },
    { key: 'valide', label: 'Validée' },
  ] as const;

  readonly item = signal<InterruptionTransportDetail | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);

  readonly actionLabels: Record<ActionStatut, string> = {
    creation: 'Saisie',
    cloture: 'Clôturée',
    validation: 'Validée',
    renvoi_correction: 'Renvoyée en correction',
    devalidation: 'Dévalidée',
    archivage: 'Archivée (rapport mensuel)',
  };
  readonly historique = signal<StatutHistorique[]>([]);
  readonly motifAction = signal<'renvoi' | 'devalidation' | null>(null);
  readonly motifSaving = signal(false);
  readonly motifForm = this.fb.nonNullable.group({
    motif: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(1000)]],
  });
  /** Renvoi et dévalidation transport : Admin Dispatching. */
  readonly canCorriger = computed(() => this.auth.hasRole('ADMIN_DISPATCHING', 'SUPERADMIN'));
  readonly dernierRenvoi = computed((): StatutHistorique | null => {
    if (this.item()?.statut !== 'en_cours') return null;
    const last = this.historique().at(-1);
    return last?.action === 'renvoi_correction' ? last : null;
  });
  readonly maxRemise = this.toDatetimeLocal(new Date(Date.now() + 5 * 60000));

  readonly clotureForm = this.fb.nonNullable.group({
    date_remise: ['', Validators.required],
  });

  ngOnInit(): void {
    if (!this.auth.currentUser()) {
      this.auth.fetchMe().subscribe();
    }
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.load(id);
  }

  canEdit(it: InterruptionTransportDetail): boolean {
    return it.statut === 'en_cours' && this.auth.hasRole('DISPATCHER', 'ADMIN_DISPATCHING');
  }

  typeLabel(type: string): string {
    return type === 'omvg' ? 'OMVG' : 'Transport HTB';
  }

  stepDone(stepKey: string, current: string): boolean {
    const order = ['en_cours', 'cloture', 'valide', 'archive'];
    return order.indexOf(current) > order.indexOf(stepKey);
  }

  cloturer(): void {
    const it = this.item();
    if (!it || this.clotureForm.invalid) return;
    const dateIso = new Date(this.clotureForm.value.date_remise!).toISOString();
    this.actionError.set(null);
    this.service.cloturer(it.id, { date_remise: dateIso }).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  valider(): void {
    const it = this.item();
    if (!it) return;
    this.actionError.set(null);
    this.service.valider(it.id).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  ouvrirMotif(action: 'renvoi' | 'devalidation'): void {
    this.motifForm.reset();
    this.actionError.set(null);
    this.motifAction.set(action);
  }

  annulerMotif(): void {
    this.motifAction.set(null);
  }

  confirmerMotif(): void {
    const it = this.item();
    const action = this.motifAction();
    if (!it || !action) return;
    if (this.motifForm.invalid) {
      this.motifForm.markAllAsTouched();
      return;
    }
    const body = { motif: this.motifForm.getRawValue().motif.trim() };
    this.motifSaving.set(true);
    const call =
      action === 'renvoi' ? this.service.renvoyer(it.id, body) : this.service.devalider(it.id, body);
    call.subscribe({
      next: () => {
        this.motifSaving.set(false);
        this.motifAction.set(null);
        this.load(it.id);
      },
      error: (err: Error) => {
        this.motifSaving.set(false);
        this.actionError.set(err.message);
      },
    });
  }

  private toDatetimeLocal(d: Date): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  private load(id: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.get(id).subscribe({
      next: (detail) => {
        this.item.set(detail);
        this.loading.set(false);
        this.service.historiqueStatuts(id).subscribe({
          next: (h) => this.historique.set(h),
          error: () => this.historique.set([]),
        });
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }
}
