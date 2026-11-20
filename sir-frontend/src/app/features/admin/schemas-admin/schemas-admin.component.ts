import { Component, ViewChild, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Subject, catchError, debounceTime, of, switchMap } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AuthService } from '../../../core/auth/auth.service';
import { Poste } from '../../../shared/models/reseau.models';
import { PosteSchema, SchemaUnifilaire } from '../../../shared/models/schema-unifilaire.models';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { ReseauDistributionService } from '../../interruptions-distribution/services/reseau-distribution.service';
import { SchemaUnifilaireService } from '../../schemas-unifilaires/schema-unifilaire.service';
import { EtatPoste, SchemaViewerComponent } from '../../schemas-unifilaires/schema-viewer/schema-viewer.component';

type Filtre = 'aucun' | 'non-relies' | 'ambigus';

/**
 * Administration → Schémas unifilaires : consultation des schémas importés et rapprochement de leurs
 * postes avec les postes SIRV2 (Admin SCR). L'import se fait par script depuis le PDF AutoCAD.
 */
@Component({
  selector: 'sir-schemas-admin',
  standalone: true,
  imports: [DatePipe, DecimalPipe, PageHeaderComponent, AdminNavComponent, SchemaViewerComponent],
  templateUrl: './schemas-admin.component.html',
  styleUrl: './schemas-admin.component.scss',
})
export class SchemasAdminComponent {
  private readonly service = inject(SchemaUnifilaireService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly auth = inject(AuthService);

  @ViewChild(SchemaViewerComponent) private viewer?: SchemaViewerComponent;

  readonly schemas = signal<SchemaUnifilaire[]>([]);
  readonly schema = signal<SchemaUnifilaire | null>(null);
  readonly postes = signal<PosteSchema[]>([]);
  readonly chargement = signal(true);
  readonly erreur = signal<string | null>(null);
  readonly choisi = signal<PosteSchema | null>(null);
  readonly filtre = signal<Filtre>('aucun');
  readonly recherche = signal('');
  readonly candidats = signal<Poste[]>([]);
  readonly envoi = signal(false);
  readonly canAssocier = computed(() => {
    this.auth.currentUser();
    return this.auth.hasRole('ADMIN_SCR');
  });

  private readonly recherche$ = new Subject<string>();

  readonly compteurs = computed(() => {
    const liste = this.postes();
    return {
      total: liste.length,
      relies: liste.filter((p) => p.poste_id !== null).length,
      ambigus: liste.filter((p) => p.rapprochement === 'ambigu').length,
      sansNom: liste.filter((p) => !p.libelle).length,
    };
  });

  readonly etats = computed((): ReadonlyMap<number, EtatPoste> => {
    const etats = new Map<number, EtatPoste>();
    const f = this.filtre();
    if (f !== 'aucun') {
      for (const p of this.postes()) {
        if (f === 'non-relies' && p.poste_id === null) etats.set(p.id, 'non-relie');
        if (f === 'ambigus' && p.rapprochement === 'ambigu') etats.set(p.id, 'non-relie');
      }
    }
    const c = this.choisi();
    if (c) etats.set(c.id, 'focus');
    return etats;
  });

  readonly resultatsSchema = computed(() => {
    const q = this.recherche().trim().toLowerCase();
    if (q.length < 2) return [];
    return this.postes()
      .filter((p) => (p.libelle ?? '').toLowerCase().includes(q))
      .slice(0, 8);
  });

  constructor() {
    this.service.lister().subscribe({
      next: (liste) => {
        this.schemas.set(liste);
        if (liste.length > 0) this.ouvrir(liste[0]);
        else this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
    this.recherche$
      .pipe(
        debounceTime(300),
        switchMap((q) =>
          q.trim().length < 2
            ? of<Poste[]>([])
            : this.reseau.listPostes({ q: q.trim(), page: 1, page_size: 10 }).pipe(
                switchMap((res) => of(res.items)),
                catchError(() => of<Poste[]>([])),
              ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe((postes) => this.candidats.set(postes));
  }

  ouvrir(schema: SchemaUnifilaire): void {
    this.schema.set(schema);
    this.choisi.set(null);
    this.chargement.set(true);
    this.service.postes(schema.id).subscribe({
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

  choisirFiltre(filtre: Filtre): void {
    this.filtre.set(this.filtre() === filtre ? 'aucun' : filtre);
  }

  onPosteClique(poste: PosteSchema): void {
    this.choisi.set(poste);
    this.candidats.set([]);
    this.erreur.set(null);
    if (this.canAssocier() && poste.libelle) this.recherche$.next(poste.libelle.replace(/^H61\s*/i, ''));
  }

  onRechercheSchema(event: Event): void {
    this.recherche.set((event.target as HTMLInputElement).value);
  }

  allerA(poste: PosteSchema): void {
    this.viewer?.centrerSur(poste);
    this.onPosteClique(poste);
    this.recherche.set('');
  }

  onRechercheSirv2(event: Event): void {
    this.recherche$.next((event.target as HTMLInputElement).value);
  }

  associer(posteId: number | null): void {
    const schema = this.schema();
    const choisi = this.choisi();
    if (!schema || !choisi || this.envoi()) return;
    this.envoi.set(true);
    this.service.associer(schema.id, choisi.id, posteId).subscribe({
      next: (maj) => {
        this.postes.set(this.postes().map((p) => (p.id === maj.id ? maj : p)));
        this.choisi.set(maj);
        this.envoi.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.envoi.set(false);
      },
    });
  }
}
