import { Component, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Subject, debounceTime, distinctUntilChanged, switchMap, of, catchError } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  InterruptionDistributionDetail,
  InterruptionWorkflow,
  PosteImpacte,
  tronconSigIdFromWorkflow,
} from '../../../shared/models/interruption.models';
import { Feeder, Poste } from '../../../shared/models/reseau.models';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';
import { ReseauDistributionService } from '../services/reseau-distribution.service';

/** Ligne affichable dans la liste à cocher des postes impactés. */
export interface PosteCheckboxRow {
  posteId: number;
  libelle: string;
  code: string | null;
  feederLibelle: string | null;
  autreFeeder: boolean;
  checked: boolean;
  nombreClientsTouches: number | null;
  dateInterruption: string | null;
}

/**
 * Postes impactés d'une interruption : postes du feeder à cocher, postes d'un autre feeder du
 * même poste source, ou recherche sur tout le réseau (poste réalimenté par un autre départ).
 * Utilisé par la fiche détail et par l'écran de modification.
 */
@Component({
  selector: 'sir-postes-impactes',
  standalone: true,
  imports: [DatePipe, NgTemplateOutlet],
  templateUrl: './postes-impactes.component.html',
  styleUrl: './postes-impactes.component.scss',
})
export class PostesImpactesComponent {
  private readonly service = inject(InterruptionDistributionService);
  private readonly reseau = inject(ReseauDistributionService);

  readonly interruption = input.required<InterruptionDistributionDetail>();
  readonly workflow = input<InterruptionWorkflow | null>(null);
  readonly canWrite = input(false);
  /** Postes ajoutés ou retirés : le parent recharge la fiche. */
  readonly changed = output<void>();

  readonly catalogue = signal<Poste[]>([]);
  readonly catalogueLoading = signal(false);
  readonly feedersVoisins = signal<Feeder[]>([]);
  /** Feeder dont la liste est affichée (celui de l'interruption par défaut). */
  readonly feederAffiche = signal<number | null>(null);
  readonly filtre = signal('');
  readonly rechercheReseau = signal('');
  readonly resultatsReseau = signal<Poste[]>([]);
  readonly rechercheLoading = signal(false);
  readonly toggling = signal<ReadonlySet<number>>(new Set());
  readonly bulkLoading = signal(false);
  readonly erreur = signal<string | null>(null);

  private readonly recherche$ = new Subject<string>();
  private dernierFeederCharge: number | null = null;
  private dernierPosteSource: number | null = null;

  readonly hasSigTroncon = computed(() => tronconSigIdFromWorkflow(this.workflow()) !== null);
  readonly checkedCount = computed(() => this.interruption().postes_impactes.length);
  readonly surFeederInterruption = computed(
    () => (this.feederAffiche() ?? this.interruption().feeder_id) === this.interruption().feeder_id,
  );

  private readonly liesParId = computed(
    () => new Map<number, PosteImpacte>(this.interruption().postes_impactes.map((p) => [p.poste_id, p])),
  );

  /** Postes du feeder affiché + postes déjà cochés (quel que soit leur feeder), cochés en tête. */
  readonly rows = computed((): PosteCheckboxRow[] => {
    const lies = this.liesParId();
    const feederInterruption = this.interruption().feeder_id;
    const rows = new Map<number, PosteCheckboxRow>();
    for (const poste of this.catalogue()) {
      rows.set(poste.id, this.ligne(poste, lies.get(poste.id), feederInterruption));
    }
    for (const lie of lies.values()) {
      if (rows.has(lie.poste_id)) continue;
      rows.set(lie.poste_id, {
        posteId: lie.poste_id,
        libelle: lie.poste_libelle ?? lie.poste_code ?? `Poste #${lie.poste_id}`,
        code: lie.poste_code,
        feederLibelle: null,
        autreFeeder: false,
        checked: true,
        nombreClientsTouches: lie.nombre_clients_touches ?? lie.nombre_clients_estime ?? null,
        dateInterruption: lie.date_interruption ?? null,
      });
    }
    const f = this.filtre().trim().toLowerCase();
    let list = [...rows.values()];
    if (f) {
      list = list.filter(
        (r) => r.libelle.toLowerCase().includes(f) || (r.code?.toLowerCase().includes(f) ?? false),
      );
    }
    return list.sort((a, b) => {
      if (a.checked !== b.checked) return a.checked ? -1 : 1;
      return a.libelle.localeCompare(b.libelle, 'fr');
    });
  });

  readonly rowsReseau = computed((): PosteCheckboxRow[] => {
    const lies = this.liesParId();
    const feederInterruption = this.interruption().feeder_id;
    return this.resultatsReseau().map((p) => this.ligne(p, lies.get(p.id), feederInterruption));
  });

  constructor() {
    // Interruption chargée ou feeder modifié : liste du feeder et feeders voisins
    effect(
      () => {
        const it = this.interruption();
        untracked(() => this.synchroniser(it));
      },
      { allowSignalWrites: true },
    );
    this.recherche$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => {
          if (q.trim().length < 2) {
            this.rechercheLoading.set(false);
            return of<Poste[]>([]);
          }
          this.rechercheLoading.set(true);
          return this.service
            .postesCandidats(this.interruption().id, { q: q.trim() })
            .pipe(catchError(() => of<Poste[]>([])));
        }),
        takeUntilDestroyed(),
      )
      .subscribe((postes) => {
        this.resultatsReseau.set(postes);
        this.rechercheLoading.set(false);
      });
  }

  private ligne(poste: Poste, lie: PosteImpacte | undefined, feederInterruption: number | null): PosteCheckboxRow {
    return {
      posteId: poste.id,
      libelle: poste.libelle,
      code: poste.code,
      feederLibelle: poste.feeder_libelle ?? null,
      autreFeeder: poste.feeder_id !== null && poste.feeder_id !== feederInterruption,
      checked: lie !== undefined,
      nombreClientsTouches: lie?.nombre_clients_touches ?? lie?.nombre_clients_estime ?? poste.nombre_clients ?? null,
      dateInterruption: lie?.date_interruption ?? null,
    };
  }

  private synchroniser(it: InterruptionDistributionDetail): void {
    if (it.feeder_id !== this.dernierFeederCharge) {
      this.dernierFeederCharge = it.feeder_id;
      this.feederAffiche.set(it.feeder_id);
      this.chargerCatalogue(it.feeder_id);
    }
    if (it.poste_source_id && it.poste_source_id !== this.dernierPosteSource) {
      this.dernierPosteSource = it.poste_source_id;
      this.reseau.listFeeders({ page: 1, page_size: 500, poste_source_id: it.poste_source_id }).subscribe({
        next: (res) => this.feedersVoisins.set(res.items),
        error: () => this.feedersVoisins.set([]),
      });
    }
  }

  private chargerCatalogue(feederId: number | null): void {
    if (!feederId) {
      this.catalogue.set([]);
      return;
    }
    this.catalogueLoading.set(true);
    this.service.postesCandidats(this.interruption().id, { feederId }).subscribe({
      next: (postes) => {
        this.catalogue.set(postes);
        this.catalogueLoading.set(false);
      },
      error: (err: Error) => {
        this.catalogue.set([]);
        this.catalogueLoading.set(false);
        this.erreur.set(err.message);
      },
    });
  }

  onFeederAfficheChange(event: Event): void {
    const id = Number((event.target as HTMLSelectElement).value) || null;
    this.feederAffiche.set(id);
    this.chargerCatalogue(id);
  }

  onFiltreInput(event: Event): void {
    this.filtre.set((event.target as HTMLInputElement).value);
  }

  onRechercheReseauInput(event: Event): void {
    const q = (event.target as HTMLInputElement).value;
    this.rechercheReseau.set(q);
    this.recherche$.next(q);
  }

  isToggling(posteId: number): boolean {
    return this.toggling().has(posteId);
  }

  onCheckboxChange(row: PosteCheckboxRow, event: Event): void {
    this.toggle(row, (event.target as HTMLInputElement).checked);
  }

  private toggle(row: PosteCheckboxRow, checked: boolean): void {
    const it = this.interruption();
    if (!this.canWrite() || this.isToggling(row.posteId) || row.checked === checked) return;
    this.erreur.set(null);
    this.toggling.set(new Set([...this.toggling(), row.posteId]));
    const fin = (): void => {
      const reste = new Set(this.toggling());
      reste.delete(row.posteId);
      this.toggling.set(reste);
    };
    const ok = (): void => {
      fin();
      this.changed.emit();
    };
    const ko = (err: Error): void => {
      fin();
      this.erreur.set(err.message);
    };
    if (checked) {
      this.service
        .addPoste(it.id, { poste_id: row.posteId, nombre_clients_touches: row.nombreClientsTouches })
        .subscribe({ next: ok, error: ko });
    } else {
      this.service.removePoste(it.id, row.posteId).subscribe({ next: ok, error: ko });
    }
  }

  toutCocher(): void {
    const it = this.interruption();
    if (!this.canWrite() || this.bulkLoading()) return;
    this.erreur.set(null);
    this.bulkLoading.set(true);
    this.service.addPostesFromFeeder(it.id).subscribe({
      next: (res) => {
        this.bulkLoading.set(false);
        if (res.added_count === 0) this.erreur.set('Aucun nouveau poste ajouté (déjà associés).');
        this.changed.emit();
      },
      error: (err: Error) => {
        this.bulkLoading.set(false);
        this.erreur.set(err.message);
      },
    });
  }

  postesDuTronconSig(): void {
    const it = this.interruption();
    const tronconSigId = tronconSigIdFromWorkflow(this.workflow());
    if (!this.canWrite() || !tronconSigId || this.bulkLoading()) return;
    this.erreur.set(null);
    this.bulkLoading.set(true);
    this.service.addPostesFromSigTroncon(it.id, { troncon_sig_id: tronconSigId }).subscribe({
      next: (res) => {
        this.bulkLoading.set(false);
        if (res.added_count === 0) this.erreur.set('Aucun poste ne correspond au tronçon SIG sélectionné.');
        this.changed.emit();
      },
      error: (err: Error) => {
        this.bulkLoading.set(false);
        this.erreur.set(err.message);
      },
    });
  }
}
