import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { HasRoleDirective } from '../../../core/auth/has-role.directive';
import {
  ActionStatut,
  InterruptionDistributionDetail,
  InterruptionWorkflow,
  StatutHistorique,
} from '../../../shared/models/interruption.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { InterruptionWorkflowPanelComponent } from '../interruption-workflow-panel/interruption-workflow-panel.component';
import { AssistantPanelComponent } from '../../assistant/assistant-panel/assistant-panel.component';
import { PostesImpactesComponent } from '../postes-impactes/postes-impactes.component';

@Component({
  selector: 'sir-interruption-detail',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    DecimalPipe,
    NgTemplateOutlet,
    HasRoleDirective,
    PageHeaderComponent,
    StatusChipComponent,
    InterruptionWorkflowPanelComponent,
    AssistantPanelComponent,
    PostesImpactesComponent,
  ],
  templateUrl: './interruption-detail.component.html',
  styleUrl: './interruption-detail.component.scss',
})
export class InterruptionDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(InterruptionDistributionService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  readonly validationSteps = [
    { key: 'en_cours', label: 'En cours' },
    { key: 'cloture', label: 'Clôturée' },
    { key: 'valide', label: 'Validée' },
    { key: 'archive', label: 'Archivée' },
  ] as const;

  /** Libellés de la frise des statuts. */
  readonly actionLabels: Record<ActionStatut, string> = {
    creation: 'Saisie',
    cloture: 'Clôturée',
    validation: 'Validée',
    renvoi_correction: 'Renvoyée en correction',
    devalidation: 'Dévalidée',
    archivage: 'Archivée (rapport mensuel)',
  };

  readonly historique = signal<StatutHistorique[]>([]);
  /** Renvoi / dévalidation : formulaire de motif ouvert. */
  readonly motifAction = signal<'renvoi' | 'devalidation' | null>(null);
  readonly motifSaving = signal(false);
  readonly motifForm = this.fb.nonNullable.group({
    motif: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(1000)]],
  });

  readonly item = signal<InterruptionDistributionDetail | null>(null);
  readonly workflow = signal<InterruptionWorkflow | null>(null);
  readonly workflowLoading = signal(true);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);

  readonly canWritePostes = computed(
    () => this.item()?.statut === 'en_cours' && this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR'),
  );

  readonly postesCheckedCount = computed(
    () => this.item()?.postes_impactes.length ?? 0,
  );

  /** Renvoi en correction et dévalidation : Admin SCR (décision SENELEC du 27/10). */
  readonly canCorriger = computed(() => this.auth.hasRole('ADMIN_SCR', 'SUPERADMIN'));

  /** Dernier renvoi en correction, affiché en tête tant que l'interruption est à corriger. */
  readonly dernierRenvoi = computed((): StatutHistorique | null => {
    if (this.item()?.statut !== 'en_cours') return null;
    const h = this.historique();
    const last = h.at(-1);
    return last?.action === 'renvoi_correction' ? last : null;
  });

  /** Date de remise maximale acceptée (pas de date future). */
  readonly maxRemise = this.toDatetimeLocal(new Date(Date.now() + 5 * 60000).toISOString());

  /** Contrôles affichés avant la clôture, au lieu d'une erreur après le clic. */
  readonly clotureChecks = computed(() => {
    const it = this.item();
    const remise = this.clotureRemise();
    const minutes =
      it && remise
        ? Math.floor((new Date(remise).getTime() - new Date(it.date_apparition).getTime()) / 60000)
        : null;
    const etapes = this.workflow()?.etapes ?? [];
    const etapesFaites = etapes.filter((e) => e.etat === 'terminee').length;
    return [
      {
        ok: minutes !== null && minutes > 0 && new Date(remise).getTime() <= Date.now() + 5 * 60000,
        label:
          minutes === null
            ? 'Date de remise à saisir'
            : minutes <= 0
              ? "Date de remise antérieure à l'apparition"
              : new Date(remise).getTime() > Date.now() + 5 * 60000
                ? 'Date de remise dans le futur'
                : `Durée : ${minutes} min`,
        bloquant: true,
      },
      {
        ok: minutes === null || minutes <= 5 || this.postesCheckedCount() > 0,
        label: `${this.postesCheckedCount()} poste(s) impacté(s) coché(s)${
          minutes !== null && minutes > 5 ? ' — au moins 1 exigé au-delà de 5 min' : ''
        }`,
        bloquant: true,
      },
      {
        ok: etapes.length > 0 && etapesFaites === etapes.length,
        label: `${etapesFaites}/${etapes.length} étapes terrain renseignées`,
        bloquant: false,
      },
      this.endPrevue(it?.puissance_coupee_mw ?? null, minutes),
    ];
  });

  /** END = puissance coupée × durée, calculée par le serveur dès la clôture. */
  private endPrevue(puissance: number | null, minutes: number | null): { ok: boolean; label: string; bloquant: boolean } {
    if (puissance === null || puissance === undefined) {
      return {
        ok: false,
        label: 'Puissance coupée non saisie : END calculée avec la puissance des postes impactés',
        bloquant: false,
      };
    }
    if (minutes === null || minutes <= 0) {
      return { ok: false, label: `END calculée à la clôture : ${puissance} MW × durée`, bloquant: false };
    }
    const heures = minutes / 60;
    const end = (puissance * heures).toLocaleString('fr-FR', { maximumFractionDigits: 3 });
    return {
      ok: true,
      label: `END calculée à la clôture : ${end} MWh (${puissance} MW × ${heures.toLocaleString('fr-FR', { maximumFractionDigits: 2 })} h)`,
      bloquant: false,
    };
  }

  readonly clotureBloquee = computed(() =>
    this.clotureChecks().some((c) => c.bloquant && !c.ok),
  );

  private readonly clotureRemise = signal('');

  readonly clotureForm = this.fb.nonNullable.group({
    date_remise: ['', Validators.required],
  });

  constructor() {
    this.clotureForm.controls.date_remise.valueChanges.subscribe((v) => this.clotureRemise.set(v));
  }

  ngOnInit(): void {
    if (!this.auth.currentUser()) {
      this.auth.fetchMe().subscribe();
    }
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.load(id);
  }

  /** Total des clients des postes impactés (ou clients MT + BT saisis à défaut). */
  clientsTouches(it: InterruptionDistributionDetail): number {
    const fromPostes = it.postes_impactes.reduce((sum, p) => sum + (p.nombre_clients_touches ?? 0), 0);
    return fromPostes || (it.nombre_clients_mt ?? 0) + (it.nombre_clients_bt ?? 0);
  }

  canEdit(it: InterruptionDistributionDetail): boolean {
    return it.statut === 'en_cours' && this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR');
  }

  canEditWorkflow(it: InterruptionDistributionDetail): boolean {
    return this.canEdit(it);
  }

  stepDone(stepKey: string, current: string): boolean {
    const order = ['en_cours', 'cloture', 'valide', 'archive'];
    return order.indexOf(current) > order.indexOf(stepKey);
  }

  onWorkflowSaved(): void {
    const it = this.item();
    if (!it) return;
    this.reloadWorkflow(it.id);
  }

  cloturer(): void {
    const it = this.item();
    if (!it || this.clotureForm.invalid) return;
    const dateIso = new Date(this.clotureForm.value.date_remise!).toISOString();
    const minutes = Math.floor(
      (new Date(dateIso).getTime() - new Date(it.date_apparition).getTime()) / 60000,
    );
    this.actionError.set(null);
    if (minutes <= 0) {
      this.actionError.set(
        "La date de remise doit être postérieure à la date d'apparition.",
      );
      return;
    }
    if (minutes > 5 && this.postesCheckedCount() === 0) {
      this.actionError.set(
        'Pour une interruption de plus de 5 minutes, au moins un poste impacté doit être coché.',
      );
      return;
    }
    this.service.cloturer(it.id, { date_remise: dateIso }).subscribe({
      next: () => this.load(it.id),
      error: (err: unknown) => this.actionError.set(this.apiErrorMessage(err)),
    });
  }

  /** L'étape « Remise » du workflow pré-remplit la date de clôture (une seule date). */
  private prefillRemise(workflow: InterruptionWorkflow): void {
    const remise = workflow.etapes.find((e) => e.code === 'remise')?.date_fin;
    if (remise && !this.clotureForm.controls.date_remise.value) {
      this.clotureForm.controls.date_remise.setValue(this.toDatetimeLocal(remise));
    }
  }

  private loadHistorique(id: number): void {
    this.service.historiqueStatuts(id).subscribe({
      next: (h) => this.historique.set(h),
      error: () => this.historique.set([]),
    });
  }

  private toDatetimeLocal(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
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

  valider(): void {
    const it = this.item();
    if (!it) return;
    this.actionError.set(null);
    this.service.valider(it.id).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  private apiErrorMessage(err: unknown): string {
    const body = err as {
      error?: { detail?: { error?: unknown }; error?: unknown };
      message?: string;
    };
    const detail = body.error?.detail?.error ?? body.error?.error;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (typeof body.message === 'string' && !body.message.startsWith('Http failure')) {
      return body.message;
    }
    return 'La clôture a échoué. Réessayez.';
  }

  private load(id: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.workflowLoading.set(true);

    forkJoin({
      detail: this.service.get(id),
      workflow: this.service.getWorkflow(id),
    }).subscribe({
      next: ({ detail, workflow }) => {
        this.item.set(detail);
        this.workflow.set(workflow);
        this.loading.set(false);
        this.workflowLoading.set(false);
        this.prefillRemise(workflow);
        this.loadHistorique(id);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
        this.workflowLoading.set(false);
      },
    });
  }

  reloadDetailQuiet(id: number): void {
    this.service.get(id).subscribe({
      next: (detail) => this.item.set(detail),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  private reloadWorkflow(id: number): void {
    this.workflowLoading.set(true);
    this.service.getWorkflow(id).subscribe({
      next: (wf) => {
        this.workflow.set(wf);
        this.workflowLoading.set(false);
      },
      error: () => this.workflowLoading.set(false),
    });
  }
}
