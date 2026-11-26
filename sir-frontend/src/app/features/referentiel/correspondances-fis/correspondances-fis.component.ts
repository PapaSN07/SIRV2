import { DatePipe } from '@angular/common';
import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subject, catchError, debounceTime, of, switchMap, tap } from 'rxjs';
import {
  CATEGORIES_FIS,
  CategorieFis,
  CorrespondanceFis,
  CorrespondanceFisCreate,
  libelleCategorieFis,
} from '../../../shared/models/correspondance-fis.models';
import { ReferentielItem } from '../../../shared/models/referentiel.models';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { CorrespondanceFisService } from '../services/correspondance-fis.service';

/** Force majeure d'une cause : vide = règle de l'import, oui, non. */
type ForceMajeureChoix = 'regle' | 'oui' | 'non';

interface RechercheCible {
  categorie: CategorieFis;
  q: string;
}

/**
 * Correspondances FIS (Admin SCR) : un libellé du fichier FIS non reconnu est associé à une
 * entrée existante du Référentiel ; l'import FIS ne crée jamais d'entrée du Référentiel.
 */
@Component({
  selector: 'sir-correspondances-fis',
  standalone: true,
  imports: [FormsModule, RouterLink, DatePipe, PageHeaderComponent, AdminNavComponent],
  templateUrl: './correspondances-fis.component.html',
  styleUrl: './correspondances-fis.component.scss',
})
export class CorrespondancesFisComponent implements OnInit {
  private readonly service = inject(CorrespondanceFisService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  readonly categories = CATEGORIES_FIS;
  readonly libelleCategorie = libelleCategorieFis;

  // Liste
  readonly filtre = signal<CategorieFis | null>(null);
  readonly items = signal<CorrespondanceFis[]>([]);
  readonly loading = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly suppressionId = signal<number | null>(null);

  // Formulaire d'ajout
  readonly formOpen = signal(false);
  readonly categorie = signal<CategorieFis>('cause');
  readonly libelleFis = signal('');
  readonly recherche = signal('');
  readonly cibles = signal<ReferentielItem[]>([]);
  readonly rechercheEnCours = signal(false);
  readonly cible = signal<ReferentielItem | null>(null);
  readonly forceMajeure = signal<ForceMajeureChoix>('regle');
  readonly saving = signal(false);
  readonly erreurForm = signal<string | null>(null);

  /** Ce qui manque pour enregistrer (affiché à côté du bouton désactivé). */
  readonly manque = computed<string | null>(() => {
    if (!this.libelleFis().trim()) return 'Saisissez le libellé FIS.';
    if (!this.cible()) return 'Choisissez l’entrée du Référentiel visée.';
    return null;
  });

  private readonly recherche$ = new Subject<RechercheCible>();

  ngOnInit(): void {
    this.recherche$
      .pipe(
        debounceTime(300),
        tap(() => this.rechercheEnCours.set(true)),
        switchMap(({ categorie, q }) =>
          this.service.rechercherCibles(categorie, q).pipe(
            catchError((err: Error) => {
              this.erreurForm.set(err.message);
              return of<ReferentielItem[]>([]);
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((items) => {
        this.cibles.set(items);
        this.rechercheEnCours.set(false);
      });

    // Lien depuis l'import FIS : catégorie et libellé pré-remplis
    const params = this.route.snapshot.queryParamMap;
    const categorie = params.get('categorie');
    const libelle = params.get('libelle');
    if (categorie && this.categories.some((c) => c.key === categorie)) {
      this.ouvrirAjout(categorie as CategorieFis, libelle ?? '');
    }

    this.charger();
  }

  onFiltre(value: string): void {
    this.filtre.set(value ? (value as CategorieFis) : null);
    this.charger();
  }

  ouvrirAjout(categorie: CategorieFis = this.filtre() ?? 'cause', libelle = ''): void {
    this.categorie.set(categorie);
    this.libelleFis.set(libelle);
    this.recherche.set('');
    this.cible.set(null);
    this.forceMajeure.set('regle');
    this.erreurForm.set(null);
    this.message.set(null);
    this.formOpen.set(true);
    this.lancerRecherche();
  }

  fermerAjout(): void {
    this.formOpen.set(false);
    this.erreurForm.set(null);
  }

  onCategorie(value: string): void {
    this.categorie.set(value as CategorieFis);
    this.cible.set(null);
    this.forceMajeure.set('regle');
    this.lancerRecherche();
  }

  onRecherche(texte: string): void {
    this.recherche.set(texte);
    this.lancerRecherche();
  }

  choisirCible(item: ReferentielItem): void {
    this.cible.set(item);
  }

  changerCible(): void {
    this.cible.set(null);
  }

  enregistrer(): void {
    const cible = this.cible();
    const libelle = this.libelleFis().trim();
    if (!cible || !libelle || this.saving()) return;

    const categorie = this.categorie();
    const body: CorrespondanceFisCreate = {
      categorie,
      libelle_fis: libelle,
      referentiel_id: cible.id,
    };
    if (categorie === 'cause' && this.forceMajeure() !== 'regle') {
      body.is_force_majeure = this.forceMajeure() === 'oui';
    }

    this.saving.set(true);
    this.erreurForm.set(null);
    this.service
      .creer(body)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (cree) => {
          this.saving.set(false);
          this.formOpen.set(false);
          this.message.set(
            `Correspondance ajoutée : « ${cree.libelle_fis} » → ${cree.referentiel_code} ${cree.referentiel_libelle}. ` +
              'Relancez le contrôle du fichier FIS pour en tenir compte.',
          );
          this.charger();
        },
        error: (err: Error) => {
          this.saving.set(false);
          this.erreurForm.set(err.message);
        },
      });
  }

  supprimer(item: CorrespondanceFis): void {
    const texte =
      `Supprimer la correspondance ${libelleCategorieFis(item.categorie).toLowerCase()} « ${item.libelle_fis} » → ` +
      `${item.referentiel_code} ${item.referentiel_libelle} ?\n\n` +
      'Les prochains imports FIS rejetteront les lignes portant ce libellé s’il n’est pas reconnu autrement.';
    if (!confirm(texte)) return;

    this.suppressionId.set(item.id);
    this.erreur.set(null);
    this.message.set(null);
    this.service
      .supprimer(item.id)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: () => {
          this.suppressionId.set(null);
          this.message.set(`Correspondance « ${item.libelle_fis} » supprimée.`);
          this.charger();
        },
        error: (err: Error) => {
          this.suppressionId.set(null);
          this.erreur.set(err.message);
        },
      });
  }

  libelleForceMajeure(valeur: boolean | null): string {
    return valeur === null ? 'Règle de l’import' : valeur ? 'Oui' : 'Non';
  }

  private lancerRecherche(): void {
    this.recherche$.next({ categorie: this.categorie(), q: this.recherche() });
  }

  private charger(): void {
    this.loading.set(true);
    this.erreur.set(null);
    this.service
      .lister(this.filtre())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (items) => {
          this.items.set(items);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.erreur.set(err.message);
          this.loading.set(false);
        },
      });
  }
}
