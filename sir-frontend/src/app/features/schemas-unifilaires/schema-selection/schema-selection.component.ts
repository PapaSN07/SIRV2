import { Component, ViewChild, computed, effect, inject, input, output, signal, untracked } from '@angular/core';
import { DecimalPipe, NgTemplateOutlet } from '@angular/common';
import { InterruptionDistributionDetail } from '../../../shared/models/interruption.models';
import { PosteSchema, PostesEntre, SchemaUnifilaire } from '../../../shared/models/schema-unifilaire.models';
import { InterruptionDistributionService } from '../../interruptions-distribution/services/interruption-distribution.service';
import { SchemaUnifilaireService } from '../schema-unifilaire.service';
import { EtatPoste, SchemaViewerComponent } from '../schema-viewer/schema-viewer.component';

type Mode = 'entre' | 'unitaire';

/** Ligne de la liste des postes proposés (cochable si le poste du schéma est relié à SIRV2). */
interface Proposition {
  poste: PosteSchema;
  groupe: 'chemin' | 'antenne' | 'derivation' | 'unitaire';
  derivation?: number;
}

/**
 * Sélection des postes impactés sur le schéma unifilaire : deux postes → tous les postes entre eux
 * (le long de la ligne, en antenne, dérivations à cocher), ou poste par poste.
 */
@Component({
  selector: 'sir-schema-selection',
  standalone: true,
  imports: [SchemaViewerComponent, DecimalPipe, NgTemplateOutlet],
  templateUrl: './schema-selection.component.html',
  styleUrl: './schema-selection.component.scss',
})
export class SchemaSelectionComponent {
  private readonly schemas = inject(SchemaUnifilaireService);
  private readonly interruptions = inject(InterruptionDistributionService);

  readonly interruption = input.required<InterruptionDistributionDetail>();
  readonly fermer = output<void>();
  /** Postes ajoutés : la fiche se recharge. */
  readonly ajoutes = output<number>();

  @ViewChild(SchemaViewerComponent) private viewer?: SchemaViewerComponent;

  readonly liste = signal<SchemaUnifilaire[]>([]);
  readonly schema = signal<SchemaUnifilaire | null>(null);
  readonly postes = signal<PosteSchema[]>([]);
  readonly chargement = signal(true);
  readonly erreur = signal<string | null>(null);
  readonly mode = signal<Mode>('entre');
  readonly debut = signal<PosteSchema | null>(null);
  readonly fin = signal<PosteSchema | null>(null);
  readonly resultat = signal<PostesEntre | null>(null);
  readonly calcul = signal(false);
  readonly unitaires = signal<PosteSchema[]>([]);
  /** Postes du schéma cochés pour l'ajout (id du poste du schéma). */
  readonly coches = signal<ReadonlySet<number>>(new Set());
  readonly recherche = signal('');
  readonly envoi = signal(false);

  /** Postes SIRV2 déjà impactés : cochés et grisés. */
  private readonly dejaImpactes = computed(
    () => new Set(this.interruption().postes_impactes.map((p) => p.poste_id)),
  );

  readonly propositions = computed((): Proposition[] => {
    if (this.mode() === 'unitaire') return this.unitaires().map((poste) => ({ poste, groupe: 'unitaire' }));
    const r = this.resultat();
    if (!r) return [];
    return [
      ...r.chemin.map((poste): Proposition => ({ poste, groupe: 'chemin' })),
      ...r.antennes.map((poste): Proposition => ({ poste, groupe: 'antenne' })),
      ...r.derivations.flatMap((d, i) => d.postes.map((poste): Proposition => ({ poste, groupe: 'derivation', derivation: i }))),
    ];
  });

  readonly aAjouter = computed(() => {
    const deja = this.dejaImpactes();
    const ids = new Set<number>();
    for (const p of this.propositions()) {
      if (this.coches().has(p.poste.id) && p.poste.poste_id !== null && !deja.has(p.poste.poste_id)) {
        ids.add(p.poste.poste_id);
      }
    }
    return [...ids];
  });

  readonly nonRelies = computed(() => this.propositions().filter((p) => p.poste.poste_id === null).length);

  readonly etats = computed((): ReadonlyMap<number, EtatPoste> => {
    const etats = new Map<number, EtatPoste>();
    const deja = this.dejaImpactes();
    for (const p of this.postes()) {
      if (p.poste_id !== null && deja.has(p.poste_id)) etats.set(p.id, 'impacte');
    }
    for (const p of this.propositions()) {
      if (this.coches().has(p.poste.id)) etats.set(p.poste.id, p.groupe === 'unitaire' ? 'selection' : 'chemin');
    }
    const d = this.debut();
    const f = this.fin();
    if (d) etats.set(d.id, 'debut');
    if (f) etats.set(f.id, 'fin');
    return etats;
  });

  readonly trace = computed(() => (this.mode() === 'entre' ? (this.resultat()?.trace ?? []) : []));

  readonly resultatsRecherche = computed(() => {
    const q = this.recherche().trim().toLowerCase();
    if (q.length < 2) return [];
    return this.postes()
      .filter((p) => (p.libelle ?? '').toLowerCase().includes(q) || (p.poste_libelle ?? '').toLowerCase().includes(q))
      .slice(0, 8);
  });

  constructor() {
    this.schemas.lister().subscribe({
      next: (liste) => {
        this.liste.set(liste);
        const region = this.interruption().region_id;
        const choisi = liste.find((s) => s.region_id !== null && s.region_id === region) ?? liste[0] ?? null;
        if (choisi) this.choisirSchema(choisi);
        else this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
    // Un nouveau résultat : chemin et antennes cochés, dérivations non cochées
    effect(
      () => {
        const r = this.resultat();
        untracked(() => {
          if (!r) return;
          this.coches.set(new Set([...r.chemin, ...r.antennes].filter((p) => p.poste_id !== null).map((p) => p.id)));
        });
      },
      { allowSignalWrites: true },
    );
  }

  onSchemaChange(event: Event): void {
    const id = Number((event.target as HTMLSelectElement).value);
    const schema = this.liste().find((s) => s.id === id);
    if (schema) this.choisirSchema(schema);
  }

  private choisirSchema(schema: SchemaUnifilaire): void {
    this.schema.set(schema);
    this.reinitialiser();
    this.unitaires.set([]);
    this.chargement.set(true);
    this.schemas.postes(schema.id).subscribe({
      next: (postes) => {
        this.postes.set(postes);
        this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
  }

  choisirMode(mode: Mode): void {
    this.mode.set(mode);
    this.reinitialiser();
  }

  reinitialiser(): void {
    this.debut.set(null);
    this.fin.set(null);
    this.resultat.set(null);
    this.erreur.set(null);
    if (this.mode() === 'entre') this.coches.set(new Set());
  }

  onPosteClique(poste: PosteSchema): void {
    this.erreur.set(null);
    if (this.mode() === 'unitaire') {
      const present = this.unitaires().some((p) => p.id === poste.id);
      this.unitaires.set(present ? this.unitaires().filter((p) => p.id !== poste.id) : [...this.unitaires(), poste]);
      const coches = new Set(this.coches());
      if (present) coches.delete(poste.id);
      else if (poste.poste_id !== null) coches.add(poste.id);
      this.coches.set(coches);
      return;
    }
    if (!this.debut() || (this.debut() && this.fin())) {
      this.debut.set(poste);
      this.fin.set(null);
      this.resultat.set(null);
      return;
    }
    if (poste.id === this.debut()!.id) return;
    this.fin.set(poste);
    this.calculer();
  }

  private calculer(): void {
    const schema = this.schema();
    const d = this.debut();
    const f = this.fin();
    if (!schema || !d || !f) return;
    this.calcul.set(true);
    this.schemas.entre(schema.id, d.id, f.id).subscribe({
      next: (r) => {
        this.resultat.set(r);
        this.calcul.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.calcul.set(false);
      },
    });
  }

  basculer(p: Proposition, event: Event): void {
    const coches = new Set(this.coches());
    if ((event.target as HTMLInputElement).checked) coches.add(p.poste.id);
    else coches.delete(p.poste.id);
    this.coches.set(coches);
  }

  cocherDerivation(index: number, coche: boolean): void {
    const coches = new Set(this.coches());
    for (const p of this.propositions()) {
      if (p.groupe === 'derivation' && p.derivation === index && p.poste.poste_id !== null) {
        if (coche) coches.add(p.poste.id);
        else coches.delete(p.poste.id);
      }
    }
    this.coches.set(coches);
  }

  estDejaImpacte(p: PosteSchema): boolean {
    return p.poste_id !== null && this.dejaImpactes().has(p.poste_id);
  }

  onRecherche(event: Event): void {
    this.recherche.set((event.target as HTMLInputElement).value);
  }

  allerA(poste: PosteSchema): void {
    this.viewer?.centrerSur(poste);
    this.recherche.set('');
  }

  ajouter(): void {
    const ids = this.aAjouter();
    if (ids.length === 0 || this.envoi()) return;
    this.envoi.set(true);
    this.interruptions.addPostesLot(this.interruption().id, ids).subscribe({
      next: (res) => {
        this.envoi.set(false);
        this.ajoutes.emit(res.added_count);
      },
      error: (err: Error) => {
        this.envoi.set(false);
        this.erreur.set(err.message);
      },
    });
  }
}
