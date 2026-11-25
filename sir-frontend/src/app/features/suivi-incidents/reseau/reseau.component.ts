import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { combineLatest, map } from 'rxjs';
import {
  FiltresIncidents,
  LigneReseau,
  NiveauReseau,
  ReseauSuivi,
} from '../../../shared/models/suivi-incidents.models';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { formatDuree, formatEnd, formatEntier, formatPart } from '../../../shared/utils/formats-indicateurs';
import { Etat, charger, filtresResolus$ } from '../services/chargement';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';

type Colonne = 'libelle' | 'nombre' | 'duree_heures' | 'end_mwh' | 'coupures_clients' | 'postes_touches';

const NIVEAUX: { cle: NiveauReseau; libelle: string; pluriel: string; filtre: keyof FiltresIncidents }[] = [
  { cle: 'poste_source', libelle: 'Poste source', pluriel: 'Postes sources', filtre: 'poste_source_id' },
  { cle: 'feeder', libelle: 'Feeder', pluriel: 'Feeders', filtre: 'feeder_id' },
];

const COLONNES: { cle: Colonne; libelle: string; num: boolean; secondaire?: boolean }[] = [
  { cle: 'nombre', libelle: 'Interruptions', num: true },
  { cle: 'duree_heures', libelle: 'Durée', num: true, secondaire: true },
  { cle: 'end_mwh', libelle: 'END', num: true },
  { cle: 'coupures_clients', libelle: 'Coupures-clients', num: true, secondaire: true },
  { cle: 'postes_touches', libelle: 'Postes touchés', num: true, secondaire: true },
];

const TAILLE_PAGE = 25;

/** Texte comparé sans accents ni casse (« pikine » trouve « PIKINE »). */
function normaliser(texte: string | null | undefined): string {
  return (texte ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

/**
 * Onglet « Réseau » : postes sources ou feeders touchés, triables, avec recherche et export
 * Excel. Un clic sur un nom filtre tout le menu.
 */
@Component({
  selector: 'sir-suivi-reseau',
  standalone: true,
  imports: [EtatComponent],
  templateUrl: './reseau.component.html',
  styleUrl: './reseau.component.scss',
})
export class ReseauComponent {
  private readonly api = inject(SuiviIncidentsService);
  private readonly destroyRef = inject(DestroyRef);
  readonly f = inject(SuiviIncidentsFiltresService);

  readonly niveaux = NIVEAUX;
  readonly colonnes = COLONNES;
  readonly formatEntier = formatEntier;
  readonly formatDuree = formatDuree;
  readonly formatEnd = formatEnd;
  readonly formatPart = formatPart;

  readonly niveau = signal<NiveauReseau>('poste_source');
  readonly etat = signal<Etat<ReseauSuivi>>({ type: 'chargement' });
  readonly recherche = signal('');
  /** Tri : null = ordre de l'API (nombre décroissant, « Non renseigné » en dernier). */
  readonly tri = signal<{ colonne: Colonne; sens: 'asc' | 'desc' } | null>(null);
  readonly page = signal(1);
  readonly export = signal<'en_cours' | null>(null);
  readonly erreurExport = signal<string | null>(null);
  private readonly relance = signal(0);

  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  constructor() {
    charger(
      combineLatest([filtresResolus$(this.filtresResolus), toObservable(this.niveau), toObservable(this.relance)]).pipe(
        map(([x, n]) => ({ x, n })),
      ),
      ({ x, n }) => this.api.getReseau(x, n),
      (e) => {
        this.etat.set(e);
        this.page.set(1);
      },
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly niveauCourant = computed(() => NIVEAUX.find((n) => n.cle === this.niveau())!);

  readonly donnees = computed(() => {
    const e = this.etat();
    return e.type === 'ok' ? e.donnees : null;
  });

  readonly filtrees = computed<LigneReseau[]>(() => {
    const lignes = this.donnees()?.lignes ?? [];
    const q = normaliser(this.recherche().trim());
    const trouvees = q
      ? lignes.filter((l) => [l.libelle, l.code, l.poste_source].some((t) => normaliser(t).includes(q)))
      : lignes;
    const tri = this.tri();
    if (!tri) return trouvees;
    const signe = tri.sens === 'asc' ? 1 : -1;
    return [...trouvees].sort((a, b) => {
      // « Non renseigné » reste en dernier quel que soit le tri
      if ((a.id === null) !== (b.id === null)) return a.id === null ? 1 : -1;
      const va = a[tri.colonne];
      const vb = b[tri.colonne];
      const c = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va).localeCompare(String(vb), 'fr');
      return c * signe || a.libelle.localeCompare(b.libelle, 'fr');
    });
  });

  readonly nombrePages = computed(() => Math.max(1, Math.ceil(this.filtrees().length / TAILLE_PAGE)));

  readonly lignesPage = computed(() => {
    const debut = (Math.min(this.page(), this.nombrePages()) - 1) * TAILLE_PAGE;
    return this.filtrees().slice(debut, debut + TAILLE_PAGE);
  });

  readonly resumePage = computed(() => {
    const n = this.filtrees().length;
    if (n === 0) return '';
    const debut = (Math.min(this.page(), this.nombrePages()) - 1) * TAILLE_PAGE;
    return `${formatEntier(debut + 1)} – ${formatEntier(Math.min(debut + TAILLE_PAGE, n))} sur ${formatEntier(n)}`;
  });

  readonly choisirNiveau = (n: NiveauReseau): void => {
    if (n === this.niveau()) return;
    this.niveau.set(n);
    this.recherche.set('');
    this.tri.set(null);
  };

  naviguerNiveau(evenement: KeyboardEvent): void {
    const pas = ['ArrowRight', 'ArrowDown'].includes(evenement.key) ? 1 : ['ArrowLeft', 'ArrowUp'].includes(evenement.key) ? -1 : 0;
    if (!pas) return;
    evenement.preventDefault();
    const i = (NIVEAUX.findIndex((n) => n.cle === this.niveau()) + pas + NIVEAUX.length) % NIVEAUX.length;
    this.choisirNiveau(NIVEAUX[i].cle);
    (evenement.currentTarget as HTMLElement | null)?.querySelectorAll<HTMLElement>('button')[i]?.focus();
  }

  chercher(valeur: string): void {
    this.recherche.set(valeur);
    this.page.set(1);
  }

  /** Nombres : décroissant d'abord ; nom : alphabétique d'abord ; 3e clic : ordre initial. */
  trier(colonne: Colonne): void {
    const t = this.tri();
    const premier = colonne === 'libelle' ? 'asc' : 'desc';
    if (!t || t.colonne !== colonne) this.tri.set({ colonne, sens: premier });
    else if (t.sens === premier) this.tri.set({ colonne, sens: premier === 'asc' ? 'desc' : 'asc' });
    else this.tri.set(null);
    this.page.set(1);
  }

  ariaSort(colonne: Colonne): 'ascending' | 'descending' | 'none' {
    const t = this.tri();
    if (!t || t.colonne !== colonne) return 'none';
    return t.sens === 'asc' ? 'ascending' : 'descending';
  }

  iconeTri(colonne: Colonne): string {
    const s = this.ariaSort(colonne);
    return s === 'ascending' ? 'arrow_upward' : s === 'descending' ? 'arrow_downward' : 'unfold_more';
  }

  allerPage(p: number): void {
    // Bornes : les boutons en bout de pages restent focalisables (aria-disabled)
    this.page.set(Math.min(Math.max(1, p), this.nombrePages()));
  }

  filtrerSur(ligne: LigneReseau): void {
    if (ligne.id === null) return;
    this.f.definir({ [this.niveauCourant().filtre]: ligne.id } as Partial<FiltresIncidents>);
  }

  exporter(): void {
    if (this.export()) return;
    this.export.set('en_cours');
    this.erreurExport.set(null);
    // Mêmes filtres que le tableau affiché (résolus par l'API)
    const filtres = this.filtresResolus() ?? this.f.effectifs();
    this.api
      .exporterReseau(filtres, this.niveau())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
      next: ({ blob, nom }) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = nom;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.export.set(null);
      },
      error: (err: unknown) => {
        const m = (err as { message?: unknown } | null)?.message;
        this.erreurExport.set(typeof m === 'string' && m ? m : 'L’export n’a pas pu être produit.');
        this.export.set(null);
      },
    });
  }

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }
}
