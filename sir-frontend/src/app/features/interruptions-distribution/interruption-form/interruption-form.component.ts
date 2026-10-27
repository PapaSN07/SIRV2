import { DatePipe } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { ReferentielService } from '../../referentiel/services/referentiel.service';
import { GeoService } from '../../geo/services/geo.service';
import {
  InterruptionDistributionDetail,
  InterruptionWorkflow,
} from '../../../shared/models/interruption.models';
import { ReferentielItem } from '../../../shared/models/referentiel.models';
import { Region } from '../../../shared/models/geo.models';
import { Feeder, PosteSource, SousFeeder } from '../../../shared/models/reseau.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { BreadcrumbItem } from '../../../shared/ui/page-header/page-header.component';
import { ReseauDistributionService } from '../services/reseau-distribution.service';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { InterruptionWorkflowPanelComponent } from '../interruption-workflow-panel/interruption-workflow-panel.component';

interface BrouillonSaisie {
  enregistreLe: string;
  regionId: number | null;
  valeurs: Record<string, unknown>;
}

@Component({
  selector: 'sir-interruption-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PageHeaderComponent, InterruptionWorkflowPanelComponent, DatePipe],
  templateUrl: './interruption-form.component.html',
  styleUrl: './interruption-form.component.scss',
})
export class InterruptionFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly interruptionService = inject(InterruptionDistributionService);
  private readonly referentiel = inject(ReferentielService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly geo = inject(GeoService);
  private readonly auth = inject(AuthService);

  readonly editId = signal<number | null>(null);
  readonly detailFeederId = signal<number | null>(null);
  readonly workflow = signal<InterruptionWorkflow | null>(null);
  readonly workflowLoading = signal(false);
  readonly isEditMode = computed(() => this.editId() !== null);

  /** BCC / BRC / ADMIN_SCR : saisie distribution. */
  readonly canWrite = computed(() => this.auth.hasRole('BCC', 'BRC', 'ADMIN_SCR'));
  readonly isBrc = computed(() => this.auth.isExactRole('BRC'));
  readonly isBcc = computed(() => this.auth.isExactRole('BCC'));
  readonly isRegionalScope = computed(() => this.isBcc() || this.isBrc());
  readonly isReadOnly = computed(() => this.isEditMode() && !this.canWrite());

  readonly pageTitle = computed(() => {
    if (!this.isEditMode()) return 'Formulaire de saisie d\'interruption';
    return this.isReadOnly() ? 'Fiche interruption' : 'Modifier l\'interruption';
  });

  readonly regions = signal<Region[]>([]);
  readonly regionId = signal<number | null>(null);
  readonly posteSourceId = signal<number | null>(null);
  readonly postesSources = signal<PosteSource[]>([]);
  readonly feeders = signal<Feeder[]>([]);
  readonly sousFeeders = signal<SousFeeder[]>([]);
  readonly serviceLibelle = signal<string | null>(null);

  readonly causes = signal<ReferentielItem[]>([]);
  readonly natures = signal<ReferentielItem[]>([]);
  readonly sieges = signal<ReferentielItem[]>([]);
  readonly signalisations = signal<ReferentielItem[]>([]);
  readonly entreprises = signal<ReferentielItem[]>([]);
  readonly prestataires = signal<ReferentielItem[]>([]);
  readonly typesEnd = signal<ReferentielItem[]>([]);
  readonly typesReseau = signal<ReferentielItem[]>([]);
  readonly loadingRef = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly saveSuccess = signal(false);

  readonly breadcrumbs = computed<BreadcrumbItem[]>(() => {
    const items: BreadcrumbItem[] = [
      { label: 'Interruptions', route: '/interruptions/distribution' },
    ];
    if (this.isEditMode()) {
      items.push({ label: 'Détail', route: `/interruptions/distribution/${this.editId()}` });
      items.push({ label: this.isReadOnly() ? 'Fiche' : 'Modifier' });
    } else {
      items.push({ label: 'Nouvelle saisie' });
    }
    return items;
  });

  readonly form = this.fb.nonNullable.group({
    date_apparition: ['', Validators.required],
    poste_source_id: [0, Validators.min(1)],
    feeder_id: [0, Validators.min(1)],
    sous_feeder_id: [0, Validators.min(1)],
    cause_id: [0, Validators.min(1)],
    nature_id: [0, Validators.min(1)],
    siege_id: [0, Validators.min(1)],
    signalisation_id: [0, Validators.min(1)],
    type_end_id: [0, Validators.min(1)],
    type_reseau_id: [0, Validators.min(1)],
    entreprise_id: [0],
    prestataire_id: [0],
    puissance_coupee_mw: [null as number | null],
    observations: [''],
    is_force_majeure: [false],
    is_fugitive: [false],
    is_programme: [false],
    tension_kv: [null as number | null],
    nombre_clients_mt: [null as number | null],
    nombre_clients_bt: [null as number | null],
    has_extension_bt: [false],
  });

  /** Brouillon de saisie conservé dans ce navigateur (coupure réseau, session expirée…). */
  readonly brouillonTrouve = signal<{ enregistreLe: string } | null>(null);
  private brouillonARestaurer: BrouillonSaisie | null = null;
  private brouillonTimer: number | undefined;

  readonly canEditWorkflow = computed(
    () => this.isEditMode() && this.canWrite(),
  );

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    const editId = idParam ? Number(idParam) : null;
    if (editId) {
      this.editId.set(editId);
    }

    this.geo.getRegions().subscribe({
      next: (r) => {
        this.regions.set(r);
        this.matchEditRegion();
      },
      error: () => {},
    });

    this.loadReferentiel('causes', 'distribution');
    this.loadReferentiel('natures');
    this.loadReferentiel('sieges', 'distribution');
    this.loadReferentiel('signalisations', 'distribution');
    this.loadReferentiel('entreprises');
    this.loadReferentiel('prestataires');
    this.loadReferentiel('types_end');
    this.loadReferentiel('types_reseaux');

    if (editId) {
      forkJoin({
        detail: this.interruptionService.get(editId),
        workflow: this.interruptionService.getWorkflow(editId),
      }).subscribe({
        next: ({ detail, workflow }) => {
          this.detailFeederId.set(detail.feeder_id);
          this.workflow.set(workflow);
          this.applyEditNetwork(detail);
          this.applyEditDetail(detail);
          if (detail.feeder_id) {
            this.reseau
              .listSousFeeders({ page: 1, page_size: 500, feeder_id: detail.feeder_id })
              .subscribe({
                next: (res) => this.sousFeeders.set(res.items),
                error: () => {},
              });
          }
          this.syncReadOnlyControls();
          this.loadingRef.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loadingRef.set(false);
        },
      });
    } else {
      this.geo.getRegions().subscribe({
        next: (r) => {
          this.regions.set(r);
          this.ensureUserThenInitCreateScope();
        },
        error: () => this.ensureUserThenInitCreateScope(),
      });
      this.bindNetworkValueChanges();
      this.preparerBrouillon();
      this.syncNetworkControls();
      this.loadingRef.set(false);
    }
  }

  /** Réagit aux changements de poste source / feeder (évite (change) + ngValue). */
  private bindNetworkValueChanges(): void {
    this.form.controls.poste_source_id.valueChanges.subscribe((id) => {
      if (this.isEditMode()) return;
      this.onPosteSourceIdChanged(id);
    });
    this.form.controls.feeder_id.valueChanges.subscribe((id) => {
      if (this.isEditMode()) return;
      this.onFeederIdChanged(id);
    });
    this.form.controls.sous_feeder_id.valueChanges.subscribe((id) => {
      if (this.isEditMode()) return;
      this.onSousFeederIdChanged(id);
    });
  }

  /** BCC/BRC : attend le profil JWT puis charge postes sources du périmètre régional. */
  private ensureUserThenInitCreateScope(): void {
    const run = (): void => {
      if (this.isRegionalScope()) {
        this.initCreateScope();
      }
    };
    if (this.auth.currentUser()) {
      run();
      return;
    }
    this.auth.fetchMe().subscribe({
      next: run,
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private initCreateScope(): void {
    const regionId = this.auth.currentUser()?.service_id;
    if (regionId === null || regionId === undefined) {
      this.error.set(
        'Périmètre régional non configuré — déconnectez-vous puis reconnectez-vous.',
      );
      return;
    }
    this.regionId.set(regionId);
    this.reseau.listPostesSources({ page: 1, page_size: 500, region_id: regionId }).subscribe({
      next: (res) => this.applyPostesSources(res.items),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private applyPostesSources(items: PosteSource[]): void {
    this.postesSources.set(items);
    if (this.restaurerCascade('poste_source_id', items)) return;
    if (this.isEditMode() || items.length !== 1) {
      return;
    }
    const id = items[0].id;
    this.posteSourceId.set(id);
    this.form.controls.poste_source_id.setValue(id, { emitEvent: true });
  }

  private onPosteSourceIdChanged(posteSourceId: number): void {
    this.posteSourceId.set(posteSourceId >= 1 ? posteSourceId : null);
    this.feeders.set([]);
    this.sousFeeders.set([]);
    this.serviceLibelle.set(null);
    if (posteSourceId < 1) {
      this.form.controls.feeder_id.setValue(0, { emitEvent: false });
      this.form.controls.sous_feeder_id.setValue(0, { emitEvent: false });
      return;
    }
    this.loadFeedersForPosteSource(posteSourceId);
  }

  private loadFeedersForPosteSource(posteSourceId: number): void {
    this.reseau.listFeeders({ page: 1, page_size: 500, poste_source_id: posteSourceId }).subscribe({
      next: (res) => this.applyFeeders(res.items),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private applyFeeders(items: Feeder[]): void {
    this.feeders.set(items);
    this.sousFeeders.set([]);
    this.form.controls.sous_feeder_id.setValue(0, { emitEvent: false });
    if (this.restaurerCascade('feeder_id', items)) return;
    if (this.isEditMode() || items.length !== 1) {
      return;
    }
    const feeder = items[0];
    this.form.controls.feeder_id.setValue(feeder.id, { emitEvent: true });
    this.serviceLibelle.set(feeder.service_libelle ?? null);
  }

  private onFeederIdChanged(feederId: number): void {
    this.sousFeeders.set([]);
    this.form.controls.sous_feeder_id.setValue(0, { emitEvent: false });
    if (feederId < 1) {
      this.serviceLibelle.set(null);
      return;
    }
    const feeder = this.feeders().find((f) => f.id === feederId);
    this.serviceLibelle.set(feeder?.service_libelle ?? null);
    this.loadSousFeedersForFeeder(feederId);
  }

  private loadSousFeedersForFeeder(feederId: number): void {
    this.reseau.listSousFeeders({ page: 1, page_size: 500, feeder_id: feederId }).subscribe({
      next: (res) => this.applySousFeeders(res.items),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private applySousFeeders(items: SousFeeder[]): void {
    this.sousFeeders.set(items);
    const control = this.form.controls.sous_feeder_id;
    if (this.isEditMode()) {
      return;
    }
    if (items.length === 0) {
      control.clearValidators();
      control.setValue(0, { emitEvent: false });
    } else {
      control.setValidators(Validators.min(1));
      if (items.length === 1) {
        control.setValue(items[0].id, { emitEvent: false });
      }
    }
    control.updateValueAndValidity({ emitEvent: false });
    this.restaurerCascade('sous_feeder_id', items);
  }

  // --- Brouillon -----------------------------------------------------------

  private cleBrouillon(): string {
    return `sir:brouillon:interruption-distribution:${this.auth.currentUser()?.id ?? 'anonyme'}`;
  }

  private lireBrouillon(): BrouillonSaisie | null {
    try {
      const brut = localStorage.getItem(this.cleBrouillon());
      return brut ? (JSON.parse(brut) as BrouillonSaisie) : null;
    } catch {
      return null;
    }
  }

  supprimerBrouillon(): void {
    this.brouillonTrouve.set(null);
    try {
      localStorage.removeItem(this.cleBrouillon());
    } catch {
      /* stockage indisponible : rien à effacer */
    }
  }

  /** Création seulement : propose le brouillon existant, puis sauvegarde à chaque modification. */
  private preparerBrouillon(): void {
    const existant = this.lireBrouillon();
    if (existant && Object.values(existant.valeurs).some((v) => v && v !== 0)) {
      this.brouillonTrouve.set({ enregistreLe: existant.enregistreLe });
    }
    this.form.valueChanges.subscribe(() => {
      if (this.brouillonTrouve()) return; // ne pas écraser un brouillon non encore traité
      window.clearTimeout(this.brouillonTimer);
      this.brouillonTimer = window.setTimeout(() => this.ecrireBrouillon(), 800);
    });
  }

  private ecrireBrouillon(): void {
    const brouillon: BrouillonSaisie = {
      enregistreLe: new Date().toISOString(),
      regionId: this.regionId(),
      valeurs: this.form.getRawValue(),
    };
    try {
      localStorage.setItem(this.cleBrouillon(), JSON.stringify(brouillon));
    } catch {
      /* navigation privée ou stockage plein : la saisie continue sans brouillon */
    }
  }

  restaurerBrouillon(): void {
    const brouillon = this.lireBrouillon();
    this.brouillonTrouve.set(null);
    if (!brouillon) return;
    const reseau = new Set(['poste_source_id', 'feeder_id', 'sous_feeder_id']);
    const autres = Object.fromEntries(Object.entries(brouillon.valeurs).filter(([k]) => !reseau.has(k)));
    this.form.patchValue(autres, { emitEvent: false });
    // Réseau : chaque liste dépend de la précédente, on rejoue la cascade au fil des chargements
    this.brouillonARestaurer = brouillon;
    if (brouillon.regionId && !this.regionSelectDisabled()) {
      this.onRegionChange(String(brouillon.regionId));
    } else if (this.postesSources().length) {
      this.restaurerCascade('poste_source_id', this.postesSources());
    }
  }

  /** Sélectionne la valeur du brouillon dès que sa liste est chargée ; true si appliquée. */
  private restaurerCascade(champ: 'poste_source_id' | 'feeder_id' | 'sous_feeder_id', items: { id: number }[]): boolean {
    const brouillon = this.brouillonARestaurer;
    if (!brouillon) return false;
    const id = Number(brouillon.valeurs[champ] ?? 0);
    if (!id || !items.some((i) => i.id === id)) {
      this.brouillonARestaurer = null;
      return false;
    }
    if (champ === 'sous_feeder_id') {
      this.brouillonARestaurer = null;
      this.form.controls.sous_feeder_id.setValue(id, { emitEvent: false });
      return true;
    }
    this.form.controls[champ].setValue(id, { emitEvent: true });
    return true;
  }

  private onSousFeederIdChanged(_sousFeederId: number): void {
    // réservé extension (ex. filtrage postes)
  }

  regionSelectDisabled(): boolean {
    return this.isEditMode() || this.isRegionalScope();
  }

  onRegionChange(value: string): void {
    const region = value ? Number(value) : null;
    this.regionId.set(region);
    this.posteSourceId.set(null);
    this.postesSources.set([]);
    this.feeders.set([]);
    this.sousFeeders.set([]);
    this.serviceLibelle.set(null);

    if (!this.isEditMode()) {
      this.form.patchValue({ poste_source_id: 0, feeder_id: 0, sous_feeder_id: 0 });
    }

    this.syncNetworkControls();

    if (region === null) {
      return;
    }

    this.reseau.listPostesSources({ page: 1, page_size: 500, region_id: region }).subscribe({
      next: (res) => this.applyPostesSources(res.items),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  onWorkflowSaved(): void {
    const id = this.editId();
    if (!id) return;
    this.workflowLoading.set(true);
    this.interruptionService.getWorkflow(id).subscribe({
      next: (wf) => {
        this.workflow.set(wf);
        this.workflowLoading.set(false);
      },
      error: () => this.workflowLoading.set(false),
    });
  }

  /** Champs obligatoires encore vides, affichés au-dessus du formulaire après un essai d'envoi. */
  readonly missingFields = signal<string[]>([]);

  /**
   * Le bouton reste actif : un clic sur un formulaire incomplet indique ce qui
   * manque et amène au premier champ, au lieu d'un bouton grisé sans explication.
   */
  canSubmit(): boolean {
    return !this.saving();
  }

  private missingRequiredFields(): { id: string; label: string }[] {
    const raw = this.form.getRawValue();
    const creating = !this.isEditMode();
    const checks: { id: string; label: string; missing: boolean }[] = [
      { id: 'poste-source', label: 'Poste source', missing: creating && raw.poste_source_id < 1 },
      { id: 'feeder', label: 'Feeder', missing: creating && raw.feeder_id < 1 },
      {
        id: 'sous-feeder',
        label: 'Sous-feeder',
        missing: creating && this.sousFeeders().length > 0 && raw.sous_feeder_id < 1,
      },
      { id: 'date-apparition', label: "Date d'apparition", missing: !raw.date_apparition },
      { id: 'cause', label: 'Cause', missing: raw.cause_id < 1 },
      { id: 'nature', label: 'Nature', missing: raw.nature_id < 1 },
      { id: 'siege', label: 'Siège', missing: raw.siege_id < 1 },
      { id: 'signalisation', label: 'Signalisation', missing: raw.signalisation_id < 1 },
      { id: 'type-end', label: 'Type END', missing: raw.type_end_id < 1 },
      { id: 'type-reseau', label: 'Type réseau', missing: raw.type_reseau_id < 1 },
    ];
    return checks.filter((c) => c.missing);
  }

  private showMissingFields(missing: { id: string; label: string }[]): void {
    this.missingFields.set(missing.map((m) => m.label));
    this.form.markAllAsTouched();
    const first = document.getElementById(missing[0].id);
    first?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    first?.focus({ preventScroll: true });
  }

  submit(): void {
    const missing = this.missingRequiredFields();
    if (missing.length > 0) {
      this.showMissingFields(missing);
      return;
    }
    this.missingFields.set([]);
    const raw = this.form.getRawValue();
    const invalid =
      this.form.invalid ||
      (!this.isEditMode() &&
        (raw.poste_source_id < 1 ||
          raw.feeder_id < 1 ||
          (this.sousFeeders().length > 0 && raw.sous_feeder_id < 1)));
    if (invalid) return;
    this.saving.set(true);
    this.error.set(null);
    this.saveSuccess.set(false);

    const dateIso = new Date(raw.date_apparition).toISOString();
    const editId = this.editId();

    if (editId) {
      this.interruptionService
        .update(editId, {
          date_apparition: dateIso,
          cause_id: raw.cause_id,
          nature_id: raw.nature_id,
          siege_id: raw.siege_id,
          signalisation_id: raw.signalisation_id,
          type_end_id: raw.type_end_id,
          type_reseau_id: raw.type_reseau_id,
          entreprise_id: raw.entreprise_id || null,
          prestataire_id: raw.prestataire_id || null,
          puissance_coupee_mw: raw.puissance_coupee_mw,
          observations: raw.observations || null,
          is_force_majeure: raw.is_force_majeure,
          is_fugitive: raw.is_fugitive,
          is_programme: raw.is_programme,
          tension_kv: raw.tension_kv,
          nombre_clients_mt: raw.nombre_clients_mt,
          nombre_clients_bt: raw.nombre_clients_bt,
          has_extension_bt: raw.has_extension_bt,
        })
        .subscribe({
          next: () => {
            this.saving.set(false);
            this.saveSuccess.set(true);
            this.interruptionService.get(editId).subscribe({
              next: (detail) => this.applyEditDetail(detail),
            });
          },
          error: (err: Error) => {
            this.error.set(err.message);
            this.saving.set(false);
          },
        });
      return;
    }

    this.interruptionService
      .create({
        date_apparition: dateIso,
        poste_source_id: raw.poste_source_id,
        feeder_id: raw.feeder_id,
        sous_feeder_id: raw.sous_feeder_id >= 1 ? raw.sous_feeder_id : null,
        cause_id: raw.cause_id,
        nature_id: raw.nature_id,
        siege_id: raw.siege_id,
        signalisation_id: raw.signalisation_id,
        type_end_id: raw.type_end_id,
        type_reseau_id: raw.type_reseau_id,
        entreprise_id: raw.entreprise_id || null,
        prestataire_id: raw.prestataire_id || null,
        puissance_coupee_mw: raw.puissance_coupee_mw,
        observations: raw.observations || null,
        is_force_majeure: raw.is_force_majeure,
        is_fugitive: raw.is_fugitive,
        is_programme: raw.is_programme,
        tension_kv: raw.tension_kv,
        nombre_clients_mt: raw.nombre_clients_mt,
        nombre_clients_bt: raw.nombre_clients_bt,
        has_extension_bt: raw.has_extension_bt,
      })
      .subscribe({
        next: (created) => {
          this.supprimerBrouillon();
          void this.router.navigate(['/interruptions/distribution', created.id]);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
  }

  /**
   * Édition : le réseau est verrouillé, mais chaque liste doit afficher la valeur enregistrée
   * (région, poste source, feeders du même poste source).
   */
  private editRegionLibelle: string | null = null;

  /** Les régions et la fiche arrivent dans un ordre quelconque : on rapproche dès que les deux sont là. */
  private matchEditRegion(): void {
    if (!this.editRegionLibelle) return;
    const region = this.regions().find((r) => r.libelle === this.editRegionLibelle);
    if (region) this.regionId.set(region.id);
  }

  private applyEditNetwork(detail: InterruptionDistributionDetail): void {
    this.editRegionLibelle = detail.region_libelle ?? null;
    this.matchEditRegion();
    const region = this.regions().find((r) => r.libelle === detail.region_libelle);
    if (detail.poste_source_id) {
      this.postesSources.set([
        {
          id: detail.poste_source_id,
          code: '',
          libelle: detail.poste_source_libelle ?? `Poste source ${detail.poste_source_id}`,
          region_id: region?.id ?? null,
          puissance_mva: null,
          is_active: true,
        },
      ]);
      this.reseau
        .listFeeders({ page: 1, page_size: 500, poste_source_id: detail.poste_source_id })
        .subscribe({
          next: (res) => {
            this.feeders.set(res.items);
            const feeder = res.items.find((f) => f.id === detail.feeder_id);
            if (feeder?.service_libelle) this.serviceLibelle.set(feeder.service_libelle);
          },
          error: () => {},
        });
    }
  }

  private applyEditDetail(detail: InterruptionDistributionDetail): void {
    if (!this.isReadOnly() && detail.statut !== 'en_cours') {
      this.error.set('Seules les interruptions en cours peuvent être modifiées.');
      return;
    }
    const feeder = this.feeders().find((f) => f.id === detail.feeder_id);
    this.serviceLibelle.set(feeder?.service_libelle ?? detail.service_libelle);
    this.form.patchValue({
      date_apparition: this.toDatetimeLocal(detail.date_apparition),
      poste_source_id: detail.poste_source_id ?? 0,
      feeder_id: detail.feeder_id ?? 0,
      sous_feeder_id: detail.sous_feeder_id ?? 0,
      cause_id: detail.cause_id ?? 0,
      nature_id: detail.nature_id ?? 0,
      siege_id: detail.siege_id ?? 0,
      signalisation_id: detail.signalisation_id ?? 0,
      type_end_id: detail.type_end_id ?? 0,
      type_reseau_id: detail.type_reseau_id ?? 0,
      entreprise_id: detail.entreprise_id ?? 0,
      prestataire_id: detail.prestataire_id ?? 0,
      puissance_coupee_mw: detail.puissance_coupee_mw,
      observations: detail.observations ?? '',
      is_force_majeure: detail.is_force_majeure,
      is_fugitive: detail.is_fugitive,
      is_programme: detail.is_programme,
      tension_kv: detail.tension_kv,
      nombre_clients_mt: detail.nombre_clients_mt,
      nombre_clients_bt: detail.nombre_clients_bt,
      has_extension_bt: detail.has_extension_bt,
    });
    this.syncNetworkControls();
    this.syncReadOnlyControls();
  }

  /** Verrouillage réseau en édition — via FormControl (pas [disabled] dans le template). */
  private syncNetworkControls(): void {
    const posteControl = this.form.controls.poste_source_id;
    const feederControl = this.form.controls.feeder_id;
    const sousFeederControl = this.form.controls.sous_feeder_id;

    if (this.isEditMode()) {
      posteControl.disable({ emitEvent: false });
      feederControl.disable({ emitEvent: false });
      sousFeederControl.disable({ emitEvent: false });
      return;
    }

    posteControl.enable({ emitEvent: false });
    feederControl.enable({ emitEvent: false });
    sousFeederControl.enable({ emitEvent: false });
  }

  private syncReadOnlyControls(): void {
    if (!this.isReadOnly()) {
      return;
    }
    this.form.disable({ emitEvent: false });
  }

  private toDatetimeLocal(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  private loadReferentiel(
    resource:
      | 'causes'
      | 'natures'
      | 'sieges'
      | 'signalisations'
      | 'entreprises'
      | 'prestataires'
      | 'types_end'
      | 'types_reseaux',
    typeReseau?: 'distribution',
  ): void {
    this.referentiel
      .list(resource, { page: 1, page_size: 100, type_reseau: typeReseau })
      .subscribe({
        next: (res) => {
          switch (resource) {
            case 'causes':
              this.causes.set(res.items);
              break;
            case 'natures':
              this.natures.set(res.items);
              break;
            case 'sieges':
              this.sieges.set(res.items);
              break;
            case 'signalisations':
              this.signalisations.set(res.items);
              break;
            case 'entreprises':
              this.entreprises.set(res.items);
              break;
            case 'prestataires':
              this.prestataires.set(res.items);
              break;
            case 'types_end':
              this.typesEnd.set(res.items);
              break;
            case 'types_reseaux':
              this.typesReseau.set(res.items);
              break;
          }
        },
        error: () => {},
      });
  }
}
