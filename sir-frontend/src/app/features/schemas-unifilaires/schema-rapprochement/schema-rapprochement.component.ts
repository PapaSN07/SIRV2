import { Component, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, catchError, debounceTime, map, of, switchMap } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../core/auth/auth.service';
import { Feeder, Poste, PosteSource } from '../../../shared/models/reseau.models';
import {
  CompteursRapprochement,
  FiltreRapprochement,
  LigneRapprochement,
  NoeudSigCourt,
  SchemaUnifilaire,
} from '../../../shared/models/schema-unifilaire.models';
import { ReseauDistributionService } from '../../interruptions-distribution/services/reseau-distribution.service';
import { SchemaUnifilaireService } from '../schema-unifilaire.service';

/** Cellule en cours d'édition : recherche SIG ou SIR sur une ligne. */
interface Edition {
  ligneId: number;
  colonne: 'sig' | 'sir';
}

/** Recherche assistée « À créer » : poste source, feeder, poste. */
interface Creation {
  ligne: LigneRapprochement;
  posteSourceId: number | null;
  feederId: number | null;
  libelle: string;
  origine: 'sig' | 'voisins' | null;
}

const TAILLE_PAGE = 50;

/**
 * Rapprochement Schéma unifilaire / SIG / SIR (suggestion du chef de service, 23/11/2026) :
 * pour chaque poste du schéma, le nœud SIG et le poste SIR, ou la décision « Inactif » / « À créer ».
 */
@Component({
  selector: 'sir-schema-rapprochement',
  standalone: true,
  imports: [DecimalPipe, FormsModule],
  templateUrl: './schema-rapprochement.component.html',
  styleUrl: './schema-rapprochement.component.scss',
})
export class SchemaRapprochementComponent {
  private readonly service = inject(SchemaUnifilaireService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly auth = inject(AuthService);

  readonly schema = input.required<SchemaUnifilaire>();

  readonly lignes = signal<LigneRapprochement[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly filtre = signal<FiltreRapprochement>('a_traiter');
  readonly recherche = signal('');
  readonly compteurs = signal<CompteursRapprochement | null>(null);
  readonly chargement = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly envoi = signal(false);

  readonly edition = signal<Edition | null>(null);
  readonly rechercheCellule = signal('');
  readonly resultatsSig = signal<NoeudSigCourt[]>([]);
  readonly resultatsSir = signal<Poste[]>([]);

  readonly creation = signal<Creation | null>(null);
  readonly postesSources = signal<PosteSource[]>([]);
  readonly feeders = signal<Feeder[]>([]);

  readonly canRapprocher = computed(() => {
    this.auth.currentUser();
    return this.auth.hasRole('ADMIN_SCR', 'BCC', 'BRC');
  });
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / TAILLE_PAGE)));

  readonly filtres = computed((): { id: FiltreRapprochement; libelle: string; nombre: number | null }[] => {
    const c = this.compteurs();
    return [
      { id: 'a_traiter', libelle: 'À traiter', nombre: c?.a_traiter ?? null },
      { id: 'ambigus', libelle: 'Noms ambigus', nombre: c ? c.sir_ambigus + c.sig_ambigus : null },
      { id: 'sig_manquant', libelle: 'Sans nœud SIG', nombre: c ? c.total - c.sans_nom - c.sig_relies : null },
      { id: 'sir_relies', libelle: 'Reliés à SIR', nombre: c?.sir_relies ?? null },
      { id: 'a_creer', libelle: 'À créer', nombre: c?.a_creer ?? null },
      { id: 'inactifs', libelle: 'Inactifs', nombre: c?.inactifs ?? null },
      { id: 'tous', libelle: 'Tous', nombre: c?.total ?? null },
    ];
  });

  private readonly recherche$ = new Subject<string>();
  private readonly cellule$ = new Subject<{ colonne: 'sig' | 'sir'; q: string }>();

  constructor() {
    effect(
      () => {
        this.schema();
        untracked(() => {
          this.page.set(1);
          this.edition.set(null);
          this.charger();
        });
      },
      { allowSignalWrites: true },
    );
    this.recherche$.pipe(debounceTime(300), takeUntilDestroyed()).subscribe(() => {
      this.page.set(1);
      this.charger(false);
    });
    this.cellule$
      .pipe(
        debounceTime(300),
        switchMap(({ colonne, q }) => {
          if (q.trim().length < 2) return of({ colonne, sig: [] as NoeudSigCourt[], sir: [] as Poste[] });
          if (colonne === 'sig') {
            return this.service.rechercherSig(q.trim()).pipe(
              map((sig) => ({ colonne, sig, sir: [] as Poste[] })),
              catchError(() => of({ colonne, sig: [] as NoeudSigCourt[], sir: [] as Poste[] })),
            );
          }
          return this.reseau.listPostes({ q: q.trim(), page: 1, page_size: 12 }).pipe(
            map((res) => ({ colonne, sig: [] as NoeudSigCourt[], sir: res.items })),
            catchError(() => of({ colonne, sig: [] as NoeudSigCourt[], sir: [] as Poste[] })),
          );
        }),
        takeUntilDestroyed(),
      )
      .subscribe(({ sig, sir }) => {
        this.resultatsSig.set(sig);
        this.resultatsSir.set(sir);
      });
  }

  charger(avecCompteurs = true): void {
    const schema = this.schema();
    this.chargement.set(true);
    this.erreur.set(null);
    this.service.lignesRapprochement(schema.id, this.filtre(), this.recherche(), this.page(), TAILLE_PAGE).subscribe({
      next: (res) => {
        this.lignes.set(res.items);
        this.total.set(res.total);
        this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
    if (avecCompteurs) {
      this.service.compteursRapprochement(schema.id).subscribe({
        next: (c) => this.compteurs.set(c),
        error: () => {},
      });
    }
  }

  choisirFiltre(filtre: FiltreRapprochement): void {
    this.filtre.set(filtre);
    this.page.set(1);
    this.charger(false);
  }

  onRecherche(valeur: string): void {
    this.recherche.set(valeur);
    this.recherche$.next(valeur);
  }

  allerPage(page: number): void {
    if (page < 1 || page > this.pages()) return;
    this.page.set(page);
    this.charger(false);
  }

  rapprocherSig(): void {
    if (this.envoi()) return;
    this.envoi.set(true);
    this.message.set(null);
    this.service.rapprocherSig(this.schema().id).subscribe({
      next: (r) => {
        this.envoi.set(false);
        this.message.set(
          `Rapprochement SIG : ${r.relies} postes reliés, ${r.ambigus} noms portés par plusieurs nœuds, ${r.non_trouves} non trouvés. Les choix faits à la main sont gardés.`,
        );
        this.charger();
      },
      error: (err: Error) => {
        this.envoi.set(false);
        this.erreur.set(err.message);
      },
    });
  }

  // ── Édition d'une cellule ───────────────────────────────────────────────────

  editer(ligne: LigneRapprochement, colonne: 'sig' | 'sir'): void {
    this.edition.set({ ligneId: ligne.id, colonne });
    const depart = (ligne.libelle ?? '').replace(/^(poste\s+)?(hta\s+)?(h61\s+)?/i, '').trim();
    this.rechercheCellule.set(depart);
    this.resultatsSig.set([]);
    this.resultatsSir.set([]);
    this.cellule$.next({ colonne, q: depart });
  }

  enEdition(ligne: LigneRapprochement, colonne: 'sig' | 'sir'): boolean {
    const e = this.edition();
    return e !== null && e.ligneId === ligne.id && e.colonne === colonne;
  }

  onRechercheCellule(valeur: string): void {
    const e = this.edition();
    if (!e) return;
    this.rechercheCellule.set(valeur);
    this.cellule$.next({ colonne: e.colonne, q: valeur });
  }

  private remplacer(maj: LigneRapprochement): void {
    this.lignes.set(this.lignes().map((l) => (l.id === maj.id ? maj : l)));
    this.edition.set(null);
    this.envoi.set(false);
    this.service.compteursRapprochement(this.schema().id).subscribe({ next: (c) => this.compteurs.set(c), error: () => {} });
  }

  private echec(err: Error): void {
    this.envoi.set(false);
    this.erreur.set(err.message);
  }

  lierSig(ligne: LigneRapprochement, noeudId: number | null): void {
    if (this.envoi()) return;
    this.envoi.set(true);
    this.service.lierSig(this.schema().id, ligne.id, noeudId).subscribe({
      next: (maj) => this.remplacer(maj),
      error: (err: Error) => this.echec(err),
    });
  }

  lierSir(ligne: LigneRapprochement, posteId: number | null): void {
    if (this.envoi()) return;
    this.envoi.set(true);
    this.service.lierSir(this.schema().id, ligne.id, posteId).subscribe({
      next: (maj) => this.remplacer(maj),
      error: (err: Error) => this.echec(err),
    });
  }

  marquerInactif(ligne: LigneRapprochement, inactif: boolean): void {
    if (this.envoi()) return;
    this.envoi.set(true);
    this.service.statutSir(this.schema().id, ligne.id, inactif ? 'inactif' : null).subscribe({
      next: (maj) => this.remplacer(maj),
      error: (err: Error) => this.echec(err),
    });
  }

  // ── Recherche assistée « À créer » ──────────────────────────────────────────

  ouvrirCreation(ligne: LigneRapprochement): void {
    this.erreur.set(null);
    this.creation.set({ ligne, posteSourceId: null, feederId: null, libelle: ligne.libelle ?? '', origine: null });
    if (this.postesSources().length === 0) {
      this.reseau.listPostesSources({ page: 1, page_size: 500 }).subscribe({
        next: (res) => this.postesSources.set(res.items),
        error: () => {},
      });
    }
    this.service.suggestionCreation(this.schema().id, ligne.id).subscribe({
      next: (s) => {
        const c = this.creation();
        if (!c || c.ligne.id !== ligne.id) return;
        this.creation.set({ ...c, libelle: s.libelle || c.libelle, posteSourceId: s.poste_source_id, origine: s.origine });
        if (s.poste_source_id) this.chargerFeeders(s.poste_source_id, s.feeder_id);
      },
      error: () => {},
    });
  }

  private chargerFeeders(posteSourceId: number, feederId: number | null = null): void {
    this.feeders.set([]);
    this.reseau.listFeeders({ page: 1, page_size: 500, poste_source_id: posteSourceId }).subscribe({
      next: (res) => {
        this.feeders.set(res.items);
        const c = this.creation();
        if (c) this.creation.set({ ...c, feederId: res.items.some((f) => f.id === feederId) ? feederId : null });
      },
      error: () => {},
    });
  }

  onPosteSource(valeur: string): void {
    const c = this.creation();
    if (!c) return;
    const id = Number(valeur) || null;
    this.creation.set({ ...c, posteSourceId: id, feederId: null, origine: null });
    if (id) this.chargerFeeders(id);
    else this.feeders.set([]);
  }

  onFeeder(valeur: string): void {
    const c = this.creation();
    if (c) this.creation.set({ ...c, feederId: Number(valeur) || null, origine: null });
  }

  onLibelle(valeur: string): void {
    const c = this.creation();
    if (c) this.creation.set({ ...c, libelle: valeur });
  }

  validerCreation(): void {
    const c = this.creation();
    if (!c || !c.feederId || c.libelle.trim().length < 2 || this.envoi()) return;
    this.envoi.set(true);
    this.service.proposerCreation(this.schema().id, c.ligne.id, c.libelle.trim(), c.feederId).subscribe({
      next: (d) => {
        this.envoi.set(false);
        this.creation.set(null);
        this.message.set(`« ${d.libelle} » ajouté aux postes à créer (${d.feeder_libelle ?? 'feeder'}) : en attente de validation par l'Admin SCR.`);
        this.charger();
      },
      error: (err: Error) => this.echec(err),
    });
  }
}
