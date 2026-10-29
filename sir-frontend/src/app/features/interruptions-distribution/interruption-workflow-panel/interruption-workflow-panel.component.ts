import { DatePipe } from '@angular/common';
import { Component, computed, effect, inject, input, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';
import {
  ETAPE_TRONCONNEMENT,
  InterruptionWorkflow,
  WorkflowEtape,
  WorkflowEtapeUpdate,
} from '../../../shared/models/interruption.models';
import { TronconSig, TronconSigChaine } from '../../../shared/models/sig.models';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { SigService } from '../services/sig.service';
import { SigTronconPickerComponent } from '../sig-troncon-picker/sig-troncon-picker.component';

export const CLIENTS_TAB = 'clients';

/** saisi : renseigné · a_venir : étape pas encore atteinte · non_saisi : étape passée sans cette information. */
export type EtatChamp = 'saisi' | 'a_venir' | 'non_saisi';

export interface LigneRecap {
  label: string;
  valeur: string;
  etat: EtatChamp;
}

export interface GroupeRecap {
  code: string;
  titre: string;
  icone: string;
  lignes: LigneRecap[];
}

function etapeRenseignee(e: WorkflowEtape): boolean {
  return Boolean(
    e.date_debut || e.date_fin || e.responsable_matricule || e.observation || e.troncon_sig_id ||
      e.troncon_id || e.noeud_amont_libelle || e.noeud_aval_libelle,
  );
}

const ETAPE_ICONS: Record<string, string> = {
  declenchement: 'bolt',
  interpellation_pdm: 'campaign',
  tronconnement: 'content_cut',
  localisation: 'location_on',
  reparation: 'build',
  remise: 'power',
};

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
  private readonly sig = inject(SigService);

  readonly clientsTab = CLIENTS_TAB;
  readonly workflow = input<InterruptionWorkflow | null>(null);
  readonly loading = input(false);
  readonly canEdit = input(false);
  readonly interruptionId = input.required<number>();
  readonly feederId = input<number | null>(null);
  /** Aucune date d'étape ne peut précéder l'apparition de l'interruption. */
  readonly dateApparition = input<string | null>(null);
  /** Interruption clôturée : plus rien n'est « à venir », les vides sont « non saisis ». */
  readonly cloturee = input(false);

  private readonly datePipe = new DatePipe('fr-FR');

  /**
   * Récapitulatif de toutes les informations, du déclenchement aux clients.
   * Une information vide est « pas encore saisie » si son étape vient après la dernière étape
   * renseignée (le travail n'y est pas encore arrivé), « non saisie » sinon.
   */
  readonly recapitulatif = computed<GroupeRecap[]>(() => {
    const wf = this.workflow();
    if (!wf) return [];
    const etapes = wf.etapes;
    const clientsSaisis = (wf.clients?.nombre_postes_impactes ?? 0) > 0;
    let derniere = -1;
    etapes.forEach((e, i) => {
      if (etapeRenseignee(e)) derniere = i;
    });
    if (this.cloturee()) derniere = etapes.length;
    const date = (v: string | null) => (v ? this.datePipe.transform(v, 'dd/MM/yyyy HH:mm') : null);
    const ligne = (label: string, valeur: string | number | null | undefined, vide: EtatChamp): LigneRecap => {
      const texte = valeur === null || valeur === undefined || valeur === '' ? null : String(valeur);
      return {
        label,
        valeur: texte ?? (vide === 'a_venir' ? 'Pas encore saisi' : 'Non saisi'),
        etat: texte ? 'saisi' : vide,
      };
    };
    const groupes: GroupeRecap[] = etapes.map((e, i) => {
      const vide: EtatChamp = i <= derniere ? 'non_saisi' : 'a_venir';
      const lignes = [
        ligne('Début', date(e.date_debut), vide),
        ligne('Fin', date(e.date_fin), vide),
        ligne('Durée', e.duree_minutes !== null && e.duree_minutes !== undefined ? this.formatDuration(e.duree_minutes) : null, vide),
        ligne('Responsable (matricule)', e.responsable_matricule, vide),
      ];
      if (e.code === ETAPE_TRONCONNEMENT) {
        lignes.push(
          ligne('Tronçon', e.troncon_sig_libelle ?? e.troncon_libelle, vide),
          ligne('Nœud amont', e.noeud_amont_libelle, vide),
          ligne('Nœud aval', e.noeud_aval_libelle, vide),
        );
      }
      lignes.push(ligne('Observation', e.observation, vide));
      return { code: e.code, titre: e.libelle_etape_workflow, icone: this.etapeIcon(e.code), lignes };
    });
    const videClients: EtatChamp = this.cloturee() ? 'non_saisi' : 'a_venir';
    groupes.push({
      code: CLIENTS_TAB,
      titre: 'Clients',
      icone: 'groups',
      lignes: [
        ligne('Postes impactés', clientsSaisis ? wf.clients.nombre_postes_impactes : null, videClients),
        ligne(
          'Clients touchés',
          wf.clients.nombre_clients_touches !== null && wf.clients.nombre_clients_touches !== undefined
            ? wf.clients.nombre_clients_touches.toLocaleString('fr-FR')
            : null,
          videClients,
        ),
      ],
    });
    return groupes;
  });

  readonly recapCompteurs = computed(() => {
    const lignes = this.recapitulatif().flatMap((g) => g.lignes);
    return {
      saisi: lignes.filter((l) => l.etat === 'saisi').length,
      a_venir: lignes.filter((l) => l.etat === 'a_venir').length,
      non_saisi: lignes.filter((l) => l.etat === 'non_saisi').length,
    };
  });

  /** Dates saisies dans le formulaire de l'étape (suivies pour un contrôle immédiat). */
  private readonly saisieDates = signal<{ debut: string; fin: string }>({ debut: '', fin: '' });

  readonly minDebut = computed(() => toDatetimeLocal(this.dateApparition()));
  readonly maxDate = computed(() => toDatetimeLocal(new Date(Date.now() + 5 * 60000).toISOString()));
  /** La fin ne peut pas précéder le début ; le début ne peut pas précéder l'apparition. */
  readonly minFin = computed(() => this.saisieDates().debut || this.minDebut());

  readonly erreurDates = computed((): string | null => {
    const { debut, fin } = this.saisieDates();
    const apparition = this.dateApparition() ? new Date(this.dateApparition()!).getTime() : null;
    const t = (v: string) => (v ? new Date(v).getTime() : null);
    const tDebut = t(debut);
    const tFin = t(fin);
    const futur = Date.now() + 5 * 60000;
    if (tDebut !== null && tFin !== null && tFin < tDebut) {
      return 'La date de fin ne peut pas être antérieure à la date de début.';
    }
    if (apparition !== null && ((tDebut !== null && tDebut < apparition) || (tFin !== null && tFin < apparition))) {
      return "Une date d'étape ne peut pas précéder l'apparition de l'interruption.";
    }
    if ((tDebut !== null && tDebut > futur) || (tFin !== null && tFin > futur)) {
      return 'Une date d\'étape ne peut pas être dans le futur.';
    }
    return null;
  });

  readonly saved = output<void>();

  readonly activeTab = signal<string | null>(null);
  readonly saving = signal(false);
  readonly saveError = signal<string | null>(null);
  readonly tronconsSig = signal<TronconSig[]>([]);
  readonly tronconsSigTotal = signal(0);
  readonly tronconsSigLoading = signal(false);
  readonly tronconsSigError = signal<string | null>(null);
  readonly tronconSearch = signal('');
  readonly selectedAmont = signal('');
  readonly sigPickerOpen = signal(false);
  private searchTimer = 0;
  private tronconLoadSeq = 0;

  /** Toutes les étapes restent accessibles : une étape peut être passée. */
  readonly visibleEtapes = computed<WorkflowEtape[]>(() => this.workflow()?.etapes ?? []);

  readonly currentEtape = computed<WorkflowEtape | null>(() => {
    const tab = this.activeTab();
    return this.visibleEtapes().find((e) => e.code === tab) ?? null;
  });

  readonly isTronconnement = computed(() => this.currentEtape()?.code === ETAPE_TRONCONNEMENT);

  readonly noeudsAmont = computed(() => this.withCurrent(this.uniqueNoeuds('amont'), this.selectedAmont()));

  readonly noeudsAval = computed(() => {
    const amont = this.selectedAmont();
    const matches = amont
      ? this.tronconsSig().filter((t) => this.noeudKey(t.nom_noeud_amont, t.code_noeud_amont) === amont)
      : [];
    return this.withCurrent(this.uniqueFrom(matches, 'aval'), this.etapeForm.controls.noeud_aval_libelle.value);
  });

  readonly etapeForm = this.fb.nonNullable.group({
    date_debut: [''],
    date_fin: [''],
    observation: [''],
    responsable_matricule: [null as number | null],
    troncon_sig_id: [0],
    noeud_amont_libelle: [''],
    noeud_aval_libelle: [''],
  });

  constructor() {
    this.etapeForm.valueChanges.subscribe((v) =>
      this.saisieDates.set({ debut: v.date_debut ?? '', fin: v.date_fin ?? '' }),
    );
    effect(
      () => {
        const etapes = this.visibleEtapes();
        const tab = this.activeTab();
        const stillVisible = tab === CLIENTS_TAB || etapes.some((e) => e.code === tab);
        if (!stillVisible) {
          const active = etapes.find((e) => e.etat === 'active') ?? etapes[etapes.length - 1];
          this.activeTab.set(active?.code ?? CLIENTS_TAB);
        }
      },
      { allowSignalWrites: true },
    );

    effect(() => {
      const etape = this.currentEtape();
      if (etape) this.patchForm(etape);
    });

    effect(
      () => {
        const feederId = this.feederId();
        const search = this.tronconSearch();
        if (feederId) {
          const seq = ++this.tronconLoadSeq;
          this.tronconsSigLoading.set(true);
          this.tronconsSigError.set(null);
          this.sig
            .listTroncons({
              feeder_id: feederId,
              page_size: 500,
              search: search || undefined,
            })
            .subscribe({
              next: (res) => {
                if (seq !== this.tronconLoadSeq) return;
                this.tronconsSig.set(res.items);
                this.tronconsSigTotal.set(res.total);
                this.tronconsSigLoading.set(false);
              },
              error: (err: Error) => {
                if (seq !== this.tronconLoadSeq) return;
                this.tronconsSig.set([]);
                this.tronconsSigTotal.set(0);
                this.tronconsSigLoading.set(false);
                this.tronconsSigError.set(err.message);
              },
            });
        } else {
          this.tronconsSig.set([]);
          this.tronconsSigTotal.set(0);
          this.tronconsSigLoading.set(false);
          this.tronconsSigError.set(null);
        }
      },
      { allowSignalWrites: true },
    );
  }

  etapeIcon(code: string): string {
    return ETAPE_ICONS[code] ?? 'radio_button_unchecked';
  }

  selectTab(key: string): void {
    this.activeTab.set(key);
    this.saveError.set(null);
  }

  formatDuration(minutes: number | null): string {
    if (minutes == null) return '—';
    if (minutes < 60) return `${minutes} min`;
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m > 0 ? `${h} h ${m} min` : `${h} h`;
  }

  sigSegmentLabel(t: TronconSig): string {
    const amont = t.nom_noeud_amont || t.code_noeud_amont || '?';
    const aval = t.nom_noeud_aval || t.code_noeud_aval || '?';
    return `${amont} → ${aval}`;
  }

  onTronconSearchInput(event: Event): void {
    const value = (event.target as HTMLInputElement).value.trim();
    window.clearTimeout(this.searchTimer);
    this.searchTimer = window.setTimeout(() => this.tronconSearch.set(value), 300);
  }

  onNoeudAmontChange(event: Event): void {
    const amont = (event.target as HTMLSelectElement).value;
    this.selectedAmont.set(amont);
    const match = this.tronconsSig().find(
      (t) => this.noeudKey(t.nom_noeud_amont, t.code_noeud_amont) === amont,
    );
    if (!match) {
      this.etapeForm.patchValue({ noeud_aval_libelle: '', troncon_sig_id: 0 });
      return;
    }
    this.etapeForm.patchValue({
      noeud_amont_libelle: amont,
      noeud_aval_libelle: this.noeudKey(match.nom_noeud_aval, match.code_noeud_aval),
      troncon_sig_id: match.id,
    });
  }

  onNoeudAvalChange(event: Event): void {
    const aval = (event.target as HTMLSelectElement).value;
    const amont = this.selectedAmont();
    const match = this.tronconsSig().find(
      (t) =>
        this.noeudKey(t.nom_noeud_amont, t.code_noeud_amont) === amont &&
        this.noeudKey(t.nom_noeud_aval, t.code_noeud_aval) === aval,
    );
    if (match) {
      this.etapeForm.patchValue({ noeud_aval_libelle: aval, troncon_sig_id: match.id });
    }
  }

  onTronconChange(): void {
    const id = this.etapeForm.controls.troncon_sig_id.value;
    const troncon = this.tronconsSig().find((t) => t.id === id);
    if (!troncon) return;
    const amont = this.noeudKey(troncon.nom_noeud_amont, troncon.code_noeud_amont);
    this.selectedAmont.set(amont);
    this.etapeForm.patchValue({
      noeud_amont_libelle: amont,
      noeud_aval_libelle: this.noeudKey(troncon.nom_noeud_aval, troncon.code_noeud_aval),
    });
  }

  saveEtape(): void {
    const etape = this.currentEtape();
    if (!etape || this.erreurDates()) return;
    const raw = this.etapeForm.getRawValue();
    const body: WorkflowEtapeUpdate = {
      date_debut: fromDatetimeLocal(raw.date_debut),
      date_fin: fromDatetimeLocal(raw.date_fin),
      observation: raw.observation || null,
      responsable_matricule: raw.responsable_matricule || null,
    };
    if (etape.code === ETAPE_TRONCONNEMENT) {
      const sigId = raw.troncon_sig_id > 0 ? raw.troncon_sig_id : null;
      const selected = sigId ? this.tronconsSig().find((t) => t.id === sigId) : undefined;
      body.troncon_sig_id = sigId;
      body.noeud_amont_libelle =
        raw.noeud_amont_libelle || selected?.nom_noeud_amont || selected?.code_noeud_amont || null;
      body.noeud_aval_libelle =
        raw.noeud_aval_libelle || selected?.nom_noeud_aval || selected?.code_noeud_aval || null;
    }
    this.persist(etape.etape_workflow_id, body);
  }

  openSigPicker(): void {
    this.sigPickerOpen.set(true);
  }

  closeSigPicker(): void {
    this.sigPickerOpen.set(false);
  }

  onSigSelected(chain: TronconSigChaine): void {
    const etape = this.currentEtape();
    if (!etape) return;
    const t = chain.troncon;
    this.etapeForm.patchValue({
      troncon_sig_id: t.id,
      noeud_amont_libelle: t.nom_noeud_amont || t.code_noeud_amont || '',
      noeud_aval_libelle: t.nom_noeud_aval || t.code_noeud_aval || '',
    });
    this.persist(etape.etape_workflow_id, {
      troncon_sig_id: t.id,
      noeud_amont_libelle: t.nom_noeud_amont || t.code_noeud_amont || null,
      noeud_aval_libelle: t.nom_noeud_aval || t.code_noeud_aval || null,
    });
  }

  private patchForm(etape: WorkflowEtape): void {
    const amont = etape.noeud_amont_libelle ?? '';
    this.selectedAmont.set(amont);
    this.etapeForm.reset({
      date_debut: toDatetimeLocal(etape.date_debut),
      date_fin: toDatetimeLocal(etape.date_fin),
      observation: etape.observation ?? '',
      responsable_matricule: etape.responsable_matricule,
      troncon_sig_id: etape.troncon_sig_id ?? 0,
      noeud_amont_libelle: amont,
      noeud_aval_libelle: etape.noeud_aval_libelle ?? '',
    });
  }

  private noeudKey(nom: string | null, code: string | null): string {
    return (nom || code || '').trim();
  }

  private uniqueNoeuds(side: 'amont' | 'aval'): { key: string; label: string }[] {
    return this.uniqueFrom(this.tronconsSig(), side);
  }

  private uniqueFrom(rows: TronconSig[], side: 'amont' | 'aval'): { key: string; label: string }[] {
    const seen = new Set<string>();
    const items: { key: string; label: string }[] = [];
    for (const row of rows) {
      const key =
        side === 'amont'
          ? this.noeudKey(row.nom_noeud_amont, row.code_noeud_amont)
          : this.noeudKey(row.nom_noeud_aval, row.code_noeud_aval);
      if (!key || seen.has(key)) continue;
      seen.add(key);
      items.push({ key, label: key });
    }
    return items.sort((a, b) => a.label.localeCompare(b.label, 'fr'));
  }

  private withCurrent(
    options: { key: string; label: string }[],
    current: string,
  ): { key: string; label: string }[] {
    if (!current || options.some((option) => option.key === current)) return options;
    return [{ key: current, label: current }, ...options];
  }

  private persist(etapeId: number, body: WorkflowEtapeUpdate): void {
    this.saving.set(true);
    this.saveError.set(null);
    this.service.updateWorkflowEtape(this.interruptionId(), etapeId, body).subscribe({
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
