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
  PosteImpacte,
  tronconSigIdFromWorkflow,
} from '../../../shared/models/interruption.models';
import { Poste } from '../../../shared/models/reseau.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';
import { InterruptionWorkflowPanelComponent } from '../interruption-workflow-panel/interruption-workflow-panel.component';
import { AssistantPanelComponent } from '../../assistant/assistant-panel/assistant-panel.component';

/** Ligne affichable dans la liste à cocher des postes impactés. */
export interface PosteCheckboxRow {
  posteId: number;
  libelle: string;
  code: string | null;
  checked: boolean;
  nombreClientsTouches: number | null;
  dateInterruption: string | null;
}

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
    AssistantPanelComponent,
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
  readonly postesCatalogLoading = signal(false);
  readonly postesFilter = signal('');
  readonly postesToggling = signal<ReadonlySet<number>>(new Set());
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);
  readonly postesBulkLoading = signal(false);

  readonly canWritePostes = computed(
    () => this.item()?.statut === 'en_cours' && this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR'),
  );

  readonly hasSigTroncon = computed(
    () => tronconSigIdFromWorkflow(this.workflow()) !== null,
  );

  /** Postes du feeder + postes déjà liés (migration), pré-cochés si impactés. */
  readonly postesRows = computed((): PosteCheckboxRow[] => {
    const linkedById = new Map<number, PosteImpacte>(
      (this.item()?.postes_impactes ?? []).map((p) => [p.poste_id, p]),
    );
    const rows = new Map<number, PosteCheckboxRow>();

    for (const poste of this.postesCatalog()) {
      const linked = linkedById.get(poste.id);
      rows.set(poste.id, {
        posteId: poste.id,
        libelle: poste.libelle,
        code: poste.code,
        checked: linked !== undefined,
        nombreClientsTouches: linked?.nombre_clients_touches ?? poste.nombre_clients ?? null,
        dateInterruption: linked?.date_interruption ?? null,
      });
    }

    for (const linked of linkedById.values()) {
      if (rows.has(linked.poste_id)) continue;
      rows.set(linked.poste_id, {
        posteId: linked.poste_id,
        libelle: linked.poste_libelle ?? linked.poste_code ?? `Poste #${linked.poste_id}`,
        code: linked.poste_code,
        checked: true,
        nombreClientsTouches: linked.nombre_clients_touches,
        dateInterruption: linked.date_interruption ?? null,
      });
    }

    const filter = this.postesFilter().trim().toLowerCase();
    let list = [...rows.values()];
    if (filter) {
      list = list.filter(
        (r) =>
          r.libelle.toLowerCase().includes(filter) ||
          (r.code?.toLowerCase().includes(filter) ?? false),
      );
    }
    return list.sort((a, b) => {
      if (a.checked !== b.checked) return a.checked ? -1 : 1;
      return a.libelle.localeCompare(b.libelle, 'fr');
    });
  });

  readonly postesCheckedCount = computed(
    () => this.item()?.postes_impactes.length ?? 0,
  );

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

  onPostesFilterInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.postesFilter.set(value);
  }

  isPosteToggling(posteId: number): boolean {
    return this.postesToggling().has(posteId);
  }

  togglePoste(row: PosteCheckboxRow, checked: boolean): void {
    const it = this.item();
    if (!it || !this.canWritePostes() || this.isPosteToggling(row.posteId)) return;
    if (row.checked === checked) return;

    this.actionError.set(null);
    const next = new Set(this.postesToggling());
    next.add(row.posteId);
    this.postesToggling.set(next);

    const done = (): void => {
      const cleared = new Set(this.postesToggling());
      cleared.delete(row.posteId);
      this.postesToggling.set(cleared);
    };

    const onOk = (): void => {
      done();
      this.reloadDetailQuiet(it.id);
    };
    const onErr = (err: Error): void => {
      done();
      this.actionError.set(err.message);
    };

    if (checked) {
      this.service
        .addPoste(it.id, {
          poste_id: row.posteId,
          nombre_clients_touches: row.nombreClientsTouches,
        })
        .subscribe({ next: onOk, error: onErr });
    } else {
      this.service.removePoste(it.id, row.posteId).subscribe({ next: onOk, error: onErr });
    }
  }

  onPosteCheckboxChange(row: PosteCheckboxRow, event: Event): void {
    const input = event.target as HTMLInputElement;
    this.togglePoste(row, input.checked);
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
        this.reloadDetailQuiet(it.id);
      },
      error: (err: Error) => {
        this.postesBulkLoading.set(false);
        this.actionError.set(err.message);
      },
    });
  }

  addPostesFromSigTroncon(): void {
    const it = this.item();
    const tronconSigId = tronconSigIdFromWorkflow(this.workflow());
    if (!it || !this.canWritePostes() || !tronconSigId || this.postesBulkLoading()) return;
    this.actionError.set(null);
    this.postesBulkLoading.set(true);
    this.service.addPostesFromSigTroncon(it.id, { troncon_sig_id: tronconSigId }).subscribe({
      next: (res) => {
        this.postesBulkLoading.set(false);
        if (res.added_count === 0) {
          this.actionError.set('Aucun poste ne correspond au tronçon SIG sélectionné.');
        }
        this.reloadDetailQuiet(it.id);
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
        if (detail.feeder_id) {
          this.loadPostesCatalog(detail.feeder_id);
        } else {
          this.postesCatalog.set([]);
        }
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
        this.workflowLoading.set(false);
      },
    });
  }

  /** Charge tous les postes du feeder (pagination si > page_size). */
  private loadPostesCatalog(feederId: number): void {
    this.postesCatalogLoading.set(true);
    const pageSize = 500;
    this.reseau.listPostes({ feeder_id: feederId, page: 1, page_size: pageSize }).subscribe({
      next: (first) => {
        const items = [...first.items];
        const total = first.total;
        if (items.length >= total) {
          this.postesCatalog.set(items);
          this.postesCatalogLoading.set(false);
          return;
        }
        const pages = Math.ceil(total / pageSize);
        const requests = [];
        for (let page = 2; page <= pages; page++) {
          requests.push(
            this.reseau.listPostes({ feeder_id: feederId, page, page_size: pageSize }),
          );
        }
        forkJoin(requests).subscribe({
          next: (pagesRes) => {
            for (const res of pagesRes) {
              items.push(...res.items);
            }
            this.postesCatalog.set(items);
            this.postesCatalogLoading.set(false);
          },
          error: () => {
            this.postesCatalog.set(items);
            this.postesCatalogLoading.set(false);
          },
        });
      },
      error: () => {
        this.postesCatalog.set([]);
        this.postesCatalogLoading.set(false);
      },
    });
  }

  private reloadDetailQuiet(id: number): void {
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
