import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe, DecimalPipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Observable, Subject, debounceTime, distinctUntilChanged, of, switchMap, catchError } from 'rxjs';
import {
  ActionAtelier,
  DroitsAtelier,
  LienPosteUR,
  PosteRecherche,
  StatutLien,
  UniteReleveRecherche,
} from '../../../shared/models/base-clients.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';
import { BaseClientsService } from '../services/base-clients.service';

const LIBELLES_STATUT: Record<StatutLien, string> = {
  valide: 'Validé',
  ajout_propose: 'Ajout à valider',
  suppression_proposee: 'Retrait à valider',
};

/**
 * Atelier clients : rattachement des unités de relève aux postes (reprise de l'atelier SAIFI/SAIDI
 * de l'application bureau SIR). Les chefs d'unité BCC / BRC proposent, le BRC valide.
 */
@Component({
  selector: 'sir-atelier-clients',
  standalone: true,
  imports: [PageHeaderComponent, AnalyticsNavComponent, PaginatorComponent, RouterLink, DatePipe, DecimalPipe],
  templateUrl: './atelier-clients.component.html',
  styleUrl: './atelier-clients.component.scss',
})
export class AtelierClientsComponent implements OnInit {
  private readonly service = inject(BaseClientsService);
  private readonly destroyRef = inject(DestroyRef);

  readonly droits = signal<DroitsAtelier | null>(null);
  readonly liens = signal<LienPosteUR[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly pageSize = signal(50);
  readonly chargement = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly enCours = signal<number | null>(null);

  readonly recherche = signal('');
  readonly aValider = signal(false);
  readonly posteFiltre = signal<PosteRecherche | null>(null);

  // Formulaire « Rattacher une UR »
  readonly saisiePoste = signal('');
  readonly postesTrouves = signal<PosteRecherche[]>([]);
  readonly posteChoisi = signal<PosteRecherche | null>(null);
  readonly saisieUr = signal('');
  readonly urTrouvees = signal<UniteReleveRecherche[]>([]);
  readonly urChoisie = signal<UniteReleveRecherche | null>(null);

  private readonly recherchePoste$ = new Subject<string>();
  private readonly rechercheUr$ = new Subject<string>();
  private readonly rechercheListe$ = new Subject<string>();

  readonly libellesStatut = LIBELLES_STATUT;

  ngOnInit(): void {
    this.service.getDroits().subscribe({
      next: (d) => {
        this.droits.set(d);
        if (d.peut_valider) this.aValider.set(true);
        this.charger();
      },
      error: (err: Error) => this.erreur.set(err.message),
    });

    this.recherchePoste$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => (q.trim().length >= 2 ? this.service.rechercherPostes(q).pipe(catchError(() => of([]))) : of([]))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((postes) => this.postesTrouves.set(postes));

    this.rechercheUr$
      .pipe(
        debounceTime(300),
        distinctUntilChanged(),
        switchMap((q) => (q.trim().length >= 3 ? this.service.rechercherUr(q).pipe(catchError(() => of([]))) : of([]))),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((urs) => this.urTrouvees.set(urs));

    this.rechercheListe$
      .pipe(debounceTime(400), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe((q) => {
        this.recherche.set(q);
        this.page.set(1);
        this.charger();
      });
  }

  charger(): void {
    this.chargement.set(true);
    this.service
      .getLiens({
        poste_id: this.posteFiltre()?.id,
        a_valider: this.aValider(),
        recherche: this.recherche(),
        page: this.page(),
        page_size: this.pageSize(),
      })
      .subscribe({
        next: (res) => {
          this.liens.set(res.items);
          this.total.set(res.total);
          this.chargement.set(false);
        },
        error: (err: Error) => {
          this.erreur.set(err.message);
          this.chargement.set(false);
        },
      });
  }

  // ── Filtres ──

  saisirRecherche(valeur: string): void {
    this.rechercheListe$.next(valeur);
  }

  basculerAValider(valeur: boolean): void {
    this.aValider.set(valeur);
    this.page.set(1);
    this.charger();
  }

  filtrerPoste(poste: PosteRecherche | null): void {
    this.posteFiltre.set(poste);
    this.page.set(1);
    this.charger();
  }

  changerPage(page: number): void {
    this.page.set(page);
    this.charger();
  }

  changerTaille(taille: number): void {
    this.pageSize.set(taille);
    this.page.set(1);
    this.charger();
  }

  // ── Formulaire ──

  saisirPoste(valeur: string): void {
    this.saisiePoste.set(valeur);
    this.posteChoisi.set(null);
    this.recherchePoste$.next(valeur);
  }

  choisirPoste(poste: PosteRecherche): void {
    this.posteChoisi.set(poste);
    this.saisiePoste.set(`${poste.code} — ${poste.libelle}`);
    this.postesTrouves.set([]);
  }

  saisirUr(valeur: string): void {
    const ur = valeur.toUpperCase().replace(/\s/g, '');
    this.saisieUr.set(ur);
    this.urChoisie.set(null);
    this.rechercheUr$.next(ur);
  }

  choisirUr(ur: UniteReleveRecherche): void {
    this.urChoisie.set(ur);
    this.saisieUr.set(ur.unite_releve);
    this.urTrouvees.set([]);
  }

  /** Une UR absente du dernier mois chargé peut quand même être rattachée (nouvelle UR). */
  urSaisieValide(): boolean {
    return /^[0-9A-Z]{4,20}$/.test(this.saisieUr());
  }

  proposer(): void {
    const poste = this.posteChoisi();
    if (!poste || !this.urSaisieValide()) return;
    this.executer(
      0,
      this.service.proposerAjout({ poste_id: poste.id, unite_releve: this.saisieUr() }),
      () => {
        this.saisieUr.set('');
        this.urChoisie.set(null);
      },
    );
  }

  // ── Actions sur un lien ──

  retirer(lien: LienPosteUR): void {
    this.executer(lien.id, this.service.proposerRetrait(lien.id));
  }

  decider(lien: LienPosteUR, accepter: boolean): void {
    this.executer(lien.id, this.service.decider(lien.id, accepter));
  }

  private executer(id: number, appel: Observable<ActionAtelier>, apres?: () => void): void {
    this.enCours.set(id);
    this.erreur.set(null);
    this.message.set(null);
    appel.subscribe({
      next: (res) => {
        this.enCours.set(null);
        this.message.set(res.message);
        apres?.();
        this.charger();
      },
      error: (err: Error) => {
        this.enCours.set(null);
        this.erreur.set(err.message);
      },
    });
  }
}
