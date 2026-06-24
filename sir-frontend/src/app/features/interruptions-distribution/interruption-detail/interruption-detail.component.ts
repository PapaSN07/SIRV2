import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { HasRoleDirective } from '../../../core/auth/has-role.directive';
import {
  InterruptionDistributionDetail,
  InterruptionWorkflow,
} from '../../../shared/models/interruption.models';
import { Poste } from '../../../shared/models/reseau.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';
import { InterruptionWorkflowPanelComponent } from '../interruption-workflow-panel/interruption-workflow-panel.component';

@Component({
  selector: 'sir-interruption-detail',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    HasRoleDirective,
    PageHeaderComponent,
    StatusChipComponent,
    InterruptionWorkflowPanelComponent,
  ],
  templateUrl: './interruption-detail.component.html',
  styleUrl: './interruption-detail.component.scss',
})
export class InterruptionDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(InterruptionDistributionService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  readonly validationSteps = [
    { key: 'en_cours', label: 'En cours' },
    { key: 'cloture', label: 'Clôturée' },
    { key: 'valide', label: 'Validée' },
  ] as const;

  readonly item = signal<InterruptionDistributionDetail | null>(null);
  readonly workflow = signal<InterruptionWorkflow | null>(null);
  readonly workflowLoading = signal(true);
  readonly postesCatalog = signal<Poste[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly postesBulkLoading = signal(false);

  readonly canWritePostes = computed(
    () => this.item()?.statut === 'en_cours' && this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR'),
  );

  readonly hasSigTroncon = computed(
    () => (this.workflow()?.tronconnement.troncon_sig_id ?? null) !== null,
  );

  readonly availablePostes = computed(() => {
    const it = this.item();
    const linked = new Set(it?.postes_impactes.map((p) => p.poste_id) ?? []);
    return this.postesCatalog().filter((p) => !linked.has(p.id));
  });

  readonly posteForm = this.fb.nonNullable.group({
    poste_id: [0, Validators.min(1)],
    nombre_clients_touches: [null as number | null],
  });

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

  addPoste(): void {
    const it = this.item();
    if (!it || this.posteForm.invalid || !this.canWritePostes()) return;
    const raw = this.posteForm.getRawValue();
    this.actionError.set(null);
    this.service
      .addPoste(it.id, {
        poste_id: raw.poste_id,
        nombre_clients_touches: raw.nombre_clients_touches,
      })
      .subscribe({
        next: () => {
          this.posteForm.reset({ poste_id: 0, nombre_clients_touches: null });
          this.load(it.id);
        },
        error: (err: Error) => this.actionError.set(err.message),
      });
  }

  removePoste(posteId: number): void {
    const it = this.item();
    if (!it || !this.canWritePostes()) return;
    this.actionError.set(null);
    this.service.removePoste(it.id, posteId).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  addPostesFromFeeder(): void {
    const it = this.item();
    if (!it || !this.canWritePostes() || this.postesBulkLoading()) return;
    this.actionError.set(null);
    this.postesBulkLoading.set(true);
    this.service.addPostesFromFeeder(it.id).subscribe({
      next: (res) => {
        this.postesBulkLoading.set(false);
        if (res.added_count === 0) {
          this.actionError.set('Aucun nouveau poste ajouté (déjà associés ou hors périmètre).');
        }
        this.load(it.id);
      },
      error: (err: Error) => {
        this.postesBulkLoading.set(false);
        this.actionError.set(err.message);
      },
    });
  }

  addPostesFromSigTroncon(): void {
    const it = this.item();
    const tronconSigId = this.workflow()?.tronconnement.troncon_sig_id;
    if (!it || !this.canWritePostes() || !tronconSigId || this.postesBulkLoading()) return;
    this.actionError.set(null);
    this.postesBulkLoading.set(true);
    this.service.addPostesFromSigTroncon(it.id, { troncon_sig_id: tronconSigId }).subscribe({
      next: (res) => {
        this.postesBulkLoading.set(false);
        if (res.added_count === 0) {
          this.actionError.set('Aucun poste ne correspond au tronçon SIG sélectionné.');
        }
        this.load(it.id);
      },
      error: (err: Error) => {
        this.postesBulkLoading.set(false);
        this.actionError.set(err.message);
      },
    });
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
        if (detail.feeder_id) {
          this.reseau.listPostes({ feeder_id: detail.feeder_id, page_size: 100 }).subscribe({
            next: (res) => this.postesCatalog.set(res.items),
            error: () => {},
          });
        }
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
        this.workflowLoading.set(false);
      },
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
