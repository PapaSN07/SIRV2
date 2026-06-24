import { DatePipe } from '@angular/common';
import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import { InterruptionWorkflow, InterruptionWorkflowUpdate } from '../../../shared/models/interruption.models';
import { Troncon } from '../../../shared/models/reseau.models';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';
import { SigTronconPickerComponent } from '../sig-troncon-picker/sig-troncon-picker.component';
import { TronconSigChaine } from '../../../shared/models/sig.models';

export type WorkflowTabKey =
  | 'declenchement'
  | 'interpellation'
  | 'tronconnement'
  | 'localisation'
  | 'reparation'
  | 'remise'
  | 'clients';

interface WorkflowTab {
  key: WorkflowTabKey;
  label: string;
  icon: string;
}

const WORKFLOW_TABS: WorkflowTab[] = [
  { key: 'declenchement', label: 'Déclenchement', icon: 'bolt' },
  { key: 'interpellation', label: 'Interpellation', icon: 'campaign' },
  { key: 'tronconnement', label: 'Tronçonnement', icon: 'content_cut' },
  { key: 'localisation', label: 'Localisation', icon: 'location_on' },
  { key: 'reparation', label: 'Réparation', icon: 'build' },
  { key: 'remise', label: 'Remise', icon: 'power' },
  { key: 'clients', label: 'Clients', icon: 'groups' },
];

function toDatetimeLocal(value: string | null | undefined): string {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

@Component({
  selector: 'sir-interruption-workflow-panel',
  standalone: true,
  imports: [ReactiveFormsModule, DatePipe, SigTronconPickerComponent],
  templateUrl: './interruption-workflow-panel.component.html',
  styleUrl: './interruption-workflow-panel.component.scss',
})
export class InterruptionWorkflowPanelComponent {
  private readonly fb = inject(FormBuilder);
  private readonly service = inject(InterruptionDistributionService);
  private readonly reseau = inject(ReseauDistributionService);

  readonly tabs = WORKFLOW_TABS;
  readonly workflow = input<InterruptionWorkflow | null>(null);
  readonly loading = input(false);
  readonly canEdit = input(false);
  readonly interruptionId = input.required<number>();
  readonly feederId = input<number | null>(null);

  readonly saved = output<void>();

  readonly activeTab = signal<WorkflowTabKey>('declenchement');
  readonly saving = signal(false);
  readonly saveError = signal<string | null>(null);
  readonly troncons = signal<Troncon[]>([]);
  readonly sigPickerOpen = signal(false);

  readonly declenchementForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
  });

  readonly interpellationForm = this.fb.nonNullable.group({
    date_interpellation: [''],
    date_arrivee: [''],
  });

  readonly tronconnementForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
    troncon_id: [0],
    noeud_amont_libelle: [''],
    noeud_aval_libelle: [''],
  });

  readonly localisationForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
  });

  readonly reparationForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
  });

  readonly remiseForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
  });

  readonly metaForm = this.fb.nonNullable.group({
    responsable_matricule: [null as number | null],
    observations_workflow: [''],
  });

  constructor() {
    effect(() => {
      const wf = this.workflow();
      if (wf) this.patchForms(wf);
    });

    effect(() => {
      const feederId = this.feederId();
      if (feederId) {
        this.reseau.listTroncons({ feeder_id: feederId, page_size: 100 }).subscribe({
          next: (res) => this.troncons.set(res.items),
          error: () => this.troncons.set([]),
        });
      } else {
        this.troncons.set([]);
      }
    });
  }

  selectTab(key: WorkflowTabKey): void {
    this.activeTab.set(key);
    this.saveError.set(null);
  }

  tabHasData(key: WorkflowTabKey): boolean {
    const wf = this.workflow();
    if (!wf) return false;
    switch (key) {
      case 'declenchement':
        return !!(wf.declenchement.date_debut || wf.declenchement.date_fin);
      case 'interpellation':
        return !!(wf.interpellation.date_interpellation || wf.interpellation.date_arrivee);
      case 'tronconnement':
        return !!(
          wf.tronconnement.date_debut ||
          wf.tronconnement.troncon_id ||
          wf.tronconnement.noeud_amont_libelle
        );
      case 'localisation':
        return !!(wf.localisation.date_debut || wf.localisation.date_fin);
      case 'reparation':
        return !!(wf.reparation.date_debut || wf.reparation.date_fin);
      case 'remise':
        return !!(wf.remise.date_debut || wf.remise.date_fin);
      case 'clients':
        return wf.clients.nombre_postes_impactes > 0;
    }
  }

  formatDuration(minutes: number | null): string {
    if (minutes == null) return '—';
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h} h ${m} min` : `${h} h`;
  }

  saveDeclenchement(): void {
    const raw = this.declenchementForm.getRawValue();
    this.persist({
      declenchement: {
        date_debut: fromDatetimeLocal(raw.date_debut),
        date_fin: fromDatetimeLocal(raw.date_fin),
      },
    });
  }

  saveInterpellation(): void {
    const raw = this.interpellationForm.getRawValue();
    this.persist({
      interpellation: {
        date_interpellation: fromDatetimeLocal(raw.date_interpellation),
        date_arrivee: fromDatetimeLocal(raw.date_arrivee),
      },
    });
  }

  saveTronconnement(): void {
    const raw = this.tronconnementForm.getRawValue();
    this.persist({
      tronconnement: {
        date_debut: fromDatetimeLocal(raw.date_debut),
        date_fin: fromDatetimeLocal(raw.date_fin),
        troncon_id: raw.troncon_id > 0 ? raw.troncon_id : null,
        noeud_amont_libelle: raw.noeud_amont_libelle || null,
        noeud_aval_libelle: raw.noeud_aval_libelle || null,
      },
    });
  }

  openSigPicker(): void {
    this.sigPickerOpen.set(true);
  }

  closeSigPicker(): void {
    this.sigPickerOpen.set(false);
  }

  onSigSelected(chain: TronconSigChaine): void {
    const t = chain.troncon;
    this.tronconnementForm.patchValue({
      noeud_amont_libelle: t.nom_noeud_amont || t.code_noeud_amont || '',
      noeud_aval_libelle: t.nom_noeud_aval || t.code_noeud_aval || '',
    });
    this.persist({
      tronconnement: {
        troncon_sig_id: t.id,
        noeud_amont_libelle: t.nom_noeud_amont || t.code_noeud_amont || null,
        noeud_aval_libelle: t.nom_noeud_aval || t.code_noeud_aval || null,
      },
    });
  }

  saveLocalisation(): void {
    const raw = this.localisationForm.getRawValue();
    this.persist({
      localisation: {
        date_debut: fromDatetimeLocal(raw.date_debut),
        date_fin: fromDatetimeLocal(raw.date_fin),
      },
    });
  }

  saveReparation(): void {
    const raw = this.reparationForm.getRawValue();
    this.persist({
      reparation: {
        date_debut: fromDatetimeLocal(raw.date_debut),
        date_fin: fromDatetimeLocal(raw.date_fin),
      },
    });
  }

  saveRemise(): void {
    const raw = this.remiseForm.getRawValue();
    this.persist({
      remise: {
        date_debut: fromDatetimeLocal(raw.date_debut),
        date_fin: fromDatetimeLocal(raw.date_fin),
      },
    });
  }

  saveMeta(): void {
    const raw = this.metaForm.getRawValue();
    this.persist({
      responsable_matricule: raw.responsable_matricule,
      observations_workflow: raw.observations_workflow || null,
    });
  }

  private patchForms(wf: InterruptionWorkflow): void {
    this.declenchementForm.patchValue({
      date_debut: toDatetimeLocal(wf.declenchement.date_debut),
      date_fin: toDatetimeLocal(wf.declenchement.date_fin),
    });
    this.interpellationForm.patchValue({
      date_interpellation: toDatetimeLocal(wf.interpellation.date_interpellation),
      date_arrivee: toDatetimeLocal(wf.interpellation.date_arrivee),
    });
    this.tronconnementForm.patchValue({
      date_debut: toDatetimeLocal(wf.tronconnement.date_debut),
      date_fin: toDatetimeLocal(wf.tronconnement.date_fin),
      troncon_id: wf.tronconnement.troncon_id ?? 0,
      noeud_amont_libelle: wf.tronconnement.noeud_amont_libelle ?? '',
      noeud_aval_libelle: wf.tronconnement.noeud_aval_libelle ?? '',
    });
    this.localisationForm.patchValue({
      date_debut: toDatetimeLocal(wf.localisation.date_debut),
      date_fin: toDatetimeLocal(wf.localisation.date_fin),
    });
    this.reparationForm.patchValue({
      date_debut: toDatetimeLocal(wf.reparation.date_debut),
      date_fin: toDatetimeLocal(wf.reparation.date_fin),
    });
    this.remiseForm.patchValue({
      date_debut: toDatetimeLocal(wf.remise.date_debut),
      date_fin: toDatetimeLocal(wf.remise.date_fin),
    });
    this.metaForm.patchValue({
      responsable_matricule: wf.responsable_matricule,
      observations_workflow: wf.observations_workflow ?? '',
    });
  }

  private persist(body: InterruptionWorkflowUpdate): void {
    this.saving.set(true);
    this.saveError.set(null);
    this.service.updateWorkflow(this.interruptionId(), body).subscribe({
      next: () => {
        this.saving.set(false);
        this.saved.emit();
      },
      error: (err: Error) => {
        this.saving.set(false);
        this.saveError.set(err.message);
      },
    });
  }
}
