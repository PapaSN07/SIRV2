import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { InterruptionTransportDetail, TypeDirectionTransport } from '../../../shared/models/interruption-transport.models';
import { ReferentielItem } from '../../../shared/models/referentiel.models';
import {
  EquipementTransport,
  PosteLigne,
  SourceTransport,
} from '../../../shared/models/reseau-transport.models';
import { PageHeaderComponent, BreadcrumbItem } from '../../../shared/ui/page-header/page-header.component';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { ReferentielService } from '../../referentiel/services/referentiel.service';
import { InterruptionTransportService } from '../services/interruption-transport.service';
import { ReseauTransportService } from '../services/reseau-transport.service';

@Component({
  selector: 'sir-interruption-transport-form',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PageHeaderComponent, InterruptionsNavComponent],
  templateUrl: './interruption-form.component.html',
  styleUrl: './interruption-form.component.scss',
})
export class InterruptionTransportFormComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly interruptionService = inject(InterruptionTransportService);
  private readonly referentiel = inject(ReferentielService);
  private readonly reseau = inject(ReseauTransportService);

  readonly editId = signal<number | null>(null);
  readonly isEditMode = computed(() => this.editId() !== null);
  readonly typeDirections: TypeDirectionTransport[] = ['transport', 'omvg'];

  readonly equipements = signal<EquipementTransport[]>([]);
  readonly sources = signal<SourceTransport[]>([]);
  readonly postesLignes = signal<PosteLigne[]>([]);
  readonly causes = signal<ReferentielItem[]>([]);
  readonly natures = signal<ReferentielItem[]>([]);
  readonly sieges = signal<ReferentielItem[]>([]);
  readonly signalisations = signal<ReferentielItem[]>([]);
  readonly loadingRef = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly breadcrumbs = computed<BreadcrumbItem[]>(() => {
    const items: BreadcrumbItem[] = [{ label: 'Interruptions', route: '/interruptions/transport' }];
    if (this.isEditMode()) {
      items.push({ label: 'Détail', route: `/interruptions/transport/${this.editId()}` });
      items.push({ label: 'Modifier' });
    } else {
      items.push({ label: 'Nouvelle saisie' });
    }
    return items;
  });

  readonly form = this.fb.nonNullable.group({
    type_direction: ['transport' as TypeDirectionTransport, Validators.required],
    date_apparition: ['', Validators.required],
    equipement_transport_id: [0, Validators.min(1)],
    source_transport_id: [0],
    poste_ligne_id: [0],
    cause_id: [0, Validators.min(1)],
    nature_id: [0, Validators.min(1)],
    siege_id: [0, Validators.min(1)],
    signalisation_id: [0, Validators.min(1)],
    tension_kv: [null as number | null],
    puissance_transit_mw: [null as number | null],
    puissance_coupee_mw: [null as number | null],
    localisation: [''],
    observations: [''],
    is_force_majeure: [false],
    is_fugitive: [false],
  });

  ngOnInit(): void {
    const idParam = this.route.snapshot.paramMap.get('id');
    const editId = idParam ? Number(idParam) : null;
    if (editId) this.editId.set(editId);

    this.reseau.listEquipements({ page: 1, page_size: 200 }).subscribe({
      next: (res) => this.equipements.set(res.items),
    });
    this.reseau.listSources({ page: 1, page_size: 200 }).subscribe({
      next: (res) => this.sources.set(res.items),
    });
    this.reseau.listPostesLignes({ page: 1, page_size: 200 }).subscribe({
      next: (res) => this.postesLignes.set(res.items),
    });

    this.loadReferentiel('causes', 'transport');
    this.loadReferentiel('natures');
    this.loadReferentiel('sieges', 'transport');
    this.loadReferentiel('signalisations', 'transport');

    if (editId) {
      forkJoin({
        detail: this.interruptionService.get(editId),
      }).subscribe({
        next: ({ detail }) => {
          this.applyEditDetail(detail);
          this.loadingRef.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loadingRef.set(false);
        },
      });
    } else {
      this.loadingRef.set(false);
    }
  }

  posteLigneLabel(p: PosteLigne): string {
    const eq = this.equipements().find((e) => e.id === p.equipement_transport_id);
    return `#${p.id} — PS ${p.poste_source_id}${eq ? ' / ' + eq.libelle : ''}`;
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
          tension_kv: raw.tension_kv,
          puissance_transit_mw: raw.puissance_transit_mw,
          puissance_coupee_mw: raw.puissance_coupee_mw,
          localisation: raw.localisation || null,
          observations: raw.observations || null,
          is_force_majeure: raw.is_force_majeure,
          is_fugitive: raw.is_fugitive,
          source_transport_id: raw.source_transport_id > 0 ? raw.source_transport_id : null,
        })
        .subscribe({
          next: () => void this.router.navigate(['/interruptions/transport', editId]),
          error: (err: Error) => {
            this.error.set(err.message);
            this.saving.set(false);
          },
        });
      return;
    }

    this.interruptionService
      .create({
        type_direction: raw.type_direction,
        date_apparition: dateIso,
        equipement_transport_id: raw.equipement_transport_id,
        source_transport_id: raw.source_transport_id > 0 ? raw.source_transport_id : null,
        poste_ligne_id: raw.poste_ligne_id > 0 ? raw.poste_ligne_id : null,
        cause_id: raw.cause_id,
        nature_id: raw.nature_id,
        siege_id: raw.siege_id,
        signalisation_id: raw.signalisation_id,
        tension_kv: raw.tension_kv,
        puissance_transit_mw: raw.puissance_transit_mw,
        puissance_coupee_mw: raw.puissance_coupee_mw,
        localisation: raw.localisation || null,
        observations: raw.observations || null,
        is_force_majeure: raw.is_force_majeure,
        is_fugitive: raw.is_fugitive,
      })
      .subscribe({
        next: (created) => void this.router.navigate(['/interruptions/transport', created.id]),
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
  }

  private applyEditDetail(detail: InterruptionTransportDetail): void {
    if (detail.statut !== 'en_cours') {
      this.error.set('Seules les interruptions en cours peuvent être modifiées.');
      return;
    }
    this.form.patchValue({
      type_direction: detail.type_direction,
      date_apparition: this.toDatetimeLocal(detail.date_apparition),
      equipement_transport_id: detail.equipement_transport_id ?? 0,
      source_transport_id: detail.source_transport_id ?? 0,
      cause_id: detail.cause_id ?? 0,
      nature_id: detail.nature_id ?? 0,
      siege_id: detail.siege_id ?? 0,
      signalisation_id: detail.signalisation_id ?? 0,
      tension_kv: detail.tension_kv,
      puissance_transit_mw: detail.puissance_transit_mw,
      puissance_coupee_mw: detail.puissance_coupee_mw,
      localisation: detail.localisation ?? '',
      observations: detail.observations ?? '',
      is_force_majeure: detail.is_force_majeure,
      is_fugitive: detail.is_fugitive,
    });
  }

  private toDatetimeLocal(iso: string): string {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  private loadReferentiel(
    resource: 'causes' | 'natures' | 'sieges' | 'signalisations',
    typeReseau?: 'transport',
  ): void {
    this.referentiel.list(resource, { page: 1, page_size: 100, type_reseau: typeReseau }).subscribe({
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
