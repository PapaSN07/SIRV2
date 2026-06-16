import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ReferentielService } from '../../referentiel/services/referentiel.service';
import { GeoService } from '../../geo/services/geo.service';
import { InterruptionDistributionDetail } from '../../../shared/models/interruption.models';
import { ReferentielItem } from '../../../shared/models/referentiel.models';
import { Region } from '../../../shared/models/geo.models';
import { Feeder } from '../../../shared/models/reseau.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { BreadcrumbItem } from '../../../shared/ui/page-header/page-header.component';
import { ReseauDistributionService } from '../services/reseau-distribution.service';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';

@Component({
  selector: 'sir-interruption-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PageHeaderComponent],
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

  readonly editId = signal<number | null>(null);
  readonly isEditMode = computed(() => this.editId() !== null);

  readonly regions = signal<Region[]>([]);
  readonly regionId = signal<number | null>(null);
  readonly feeders = signal<Feeder[]>([]);

  readonly causes = signal<ReferentielItem[]>([]);
  readonly natures = signal<ReferentielItem[]>([]);
  readonly sieges = signal<ReferentielItem[]>([]);
  readonly signalisations = signal<ReferentielItem[]>([]);
  readonly loadingRef = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly breadcrumbs = computed<BreadcrumbItem[]>(() => {
    const items: BreadcrumbItem[] = [
      { label: 'Interruptions', route: '/interruptions/distribution' },
    ];
    if (this.isEditMode()) {
      items.push({ label: 'Détail', route: `/interruptions/distribution/${this.editId()}` });
      items.push({ label: 'Modifier' });
    } else {
      items.push({ label: 'Nouvelle saisie' });
    }
    return items;
  });

  readonly form = this.fb.nonNullable.group({
    date_apparition: ['', Validators.required],
    feeder_id: [0, Validators.min(1)],
    cause_id: [0, Validators.min(1)],
    nature_id: [0, Validators.min(1)],
    siege_id: [0, Validators.min(1)],
    signalisation_id: [0, Validators.min(1)],
    puissance_coupee_mw: [null as number | null],
    localisation: [''],
    observations: [''],
    is_force_majeure: [false],
    is_fugitive: [false],
    is_programme: [false],
  });

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    const editId = idParam ? Number(idParam) : null;
    if (editId) {
      this.editId.set(editId);
    }

    this.geo.getRegions().subscribe({
      next: (r) => this.regions.set(r),
      error: () => {},
    });

    this.loadReferentiel('causes', 'distribution');
    this.loadReferentiel('natures');
    this.loadReferentiel('sieges', 'distribution');
    this.loadReferentiel('signalisations', 'distribution');

    if (editId) {
      forkJoin({
        feeders: this.reseau.listFeeders({ page: 1, page_size: 200 }),
        detail: this.interruptionService.get(editId),
      }).subscribe({
        next: ({ feeders, detail }) => {
          this.feeders.set(feeders.items);
          this.applyEditDetail(detail);
          this.loadingRef.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loadingRef.set(false);
        },
      });
    } else {
      this.reseau.listFeeders({ page: 1, page_size: 200 }).subscribe({
        next: (res) => this.feeders.set(res.items),
      });
      this.loadingRef.set(false);
    }
  }

  onRegionChange(value: string): void {
    const region = value ? Number(value) : null;
    this.regionId.set(region);
    this.reseau
      .listFeeders({ page: 1, page_size: 200, region_id: region ?? undefined })
      .subscribe({
        next: (res) => this.feeders.set(res.items),
      });
    if (!this.isEditMode()) {
      this.form.patchValue({ feeder_id: 0 });
    }
  }

  submit(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    this.error.set(null);

    const raw = this.form.getRawValue();
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
          puissance_coupee_mw: raw.puissance_coupee_mw,
          localisation: raw.localisation || null,
          observations: raw.observations || null,
          is_force_majeure: raw.is_force_majeure,
          is_fugitive: raw.is_fugitive,
          is_programme: raw.is_programme,
        })
        .subscribe({
          next: () => {
            void this.router.navigate(['/interruptions/distribution', editId]);
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
        feeder_id: raw.feeder_id,
        cause_id: raw.cause_id,
        nature_id: raw.nature_id,
        siege_id: raw.siege_id,
        signalisation_id: raw.signalisation_id,
        puissance_coupee_mw: raw.puissance_coupee_mw,
        localisation: raw.localisation || null,
        observations: raw.observations || null,
        is_force_majeure: raw.is_force_majeure,
        is_fugitive: raw.is_fugitive,
        is_programme: raw.is_programme,
      })
      .subscribe({
        next: (created) => {
          void this.router.navigate(['/interruptions/distribution', created.id]);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
  }

  private applyEditDetail(detail: InterruptionDistributionDetail): void {
    if (detail.statut !== 'en_cours') {
      this.error.set('Seules les interruptions en cours peuvent être modifiées.');
      return;
    }
    this.form.patchValue({
      date_apparition: this.toDatetimeLocal(detail.date_apparition),
      feeder_id: detail.feeder_id ?? 0,
      cause_id: detail.cause_id ?? 0,
      nature_id: detail.nature_id ?? 0,
      siege_id: detail.siege_id ?? 0,
      signalisation_id: detail.signalisation_id ?? 0,
      puissance_coupee_mw: detail.puissance_coupee_mw,
      localisation: detail.localisation ?? '',
      observations: detail.observations ?? '',
      is_force_majeure: detail.is_force_majeure,
      is_fugitive: detail.is_fugitive,
      is_programme: detail.is_programme,
    });
  }

  private toDatetimeLocal(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  private loadReferentiel(
    resource: 'causes' | 'natures' | 'sieges' | 'signalisations',
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
          }
        },
        error: () => {},
      });
  }
}
