import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { catchError, forkJoin, map, of } from 'rxjs';
import { GeoService } from '../../geo/services/geo.service';
import { ReseauDistributionService } from '../../interruptions-distribution/services/reseau-distribution.service';
import { ReferentielService } from '../../referentiel/services/referentiel.service';
import { ModePeriode, ReseauCause } from '../../../shared/models/suivi-incidents.models';
import { dateCourte, jourMois, libelleSemaine, semaineSenelec } from '../../../shared/utils/semaine-senelec';
import { CleFiltre, SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';

interface Option {
  id: number;
  libelle: string;
}

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

const LIBELLE_CLE: Record<CleFiltre, string> = {
  region_id: 'Région',
  service_id: 'Service',
  poste_source_id: 'Poste source',
  feeder_id: 'Feeder',
  nature_id: 'Nature',
  cause_id: 'Cause',
  reseau: 'Réseau',
  exogene: 'Facteur exogène',
};

/**
 * Barre de filtres commune aux onglets du menu Suivi incidents.
 *
 * Application immédiate (pas de bouton « Appliquer ») ; les filtres actifs sont rappelés en
 * pastilles qu'on retire d'un clic. Sous 768 px, la barre se replie derrière « Filtres (n) ».
 */
@Component({
  selector: 'sir-barre-filtres',
  standalone: true,
  templateUrl: './barre-filtres.component.html',
  styleUrl: './barre-filtres.component.scss',
})
export class BarreFiltresComponent {
  readonly f = inject(SuiviIncidentsFiltresService);
  private readonly geo = inject(GeoService);
  private readonly reseau = inject(ReseauDistributionService);
  private readonly referentiel = inject(ReferentielService);
  private readonly destroyRef = inject(DestroyRef);

  readonly modes: { id: ModePeriode; libelle: string }[] = [
    { id: 'semaine', libelle: 'Semaine' },
    { id: 'mois', libelle: 'Mois' },
    { id: 'annee', libelle: 'Année' },
    { id: 'personnalise', libelle: 'Personnalisé' },
  ];

  readonly regions = signal<Option[]>([]);
  /** Services (libellé des pastilles « Service » : clic dans un onglet, service imposé). */
  readonly services = signal<Option[]>([]);
  readonly postesSources = signal<Option[]>([]);
  readonly natures = signal<Option[]>([]);
  readonly causes = signal<Option[]>([]);
  readonly listesErreur = signal(false);

  readonly plusDeFiltres = signal(false);
  /** Barre dépliée sur mobile. */
  readonly ouverte = signal(false);
  readonly personnalise = signal(false);
  /** Dernier nom de poste source saisi introuvable dans la liste. */
  readonly posteInconnu = signal(false);

  readonly modeAffiche = computed<ModePeriode>(() => (this.personnalise() ? 'personnalise' : this.f.mode()));

  /** Libellé de la période (« S47 · 14/11 → 20/11/2026 », « Novembre 2026 », « Année 2026 »). */
  readonly libellePeriode = computed(() => {
    const { debut, fin } = this.f.filtres();
    const mode = this.f.mode();
    if (mode === 'semaine') return libelleSemaine(semaineSenelec(debut));
    if (mode === 'mois') return `${MOIS[Number(debut.slice(5, 7)) - 1]} ${debut.slice(0, 4)}`;
    if (mode === 'annee') return `Année ${debut.slice(0, 4)}`;
    return `${jourMois(debut)} → ${dateCourte(fin)}`;
  });

  readonly nombreActifs = computed(() => this.f.effacables().length);

  readonly pastilles = computed(() =>
    this.f.actifs().map(({ cle, valeur }) => ({
      cle,
      libelle: LIBELLE_CLE[cle],
      valeur: this.libelleValeur(cle, valeur),
      verrouillee:
        (cle === 'region_id' && this.f.regionVerrouillee()) || (cle === 'service_id' && this.f.serviceVerrouille()),
    })),
  );

  readonly posteSourceSaisi = computed(() => {
    const id = this.f.effectifs().poste_source_id;
    return id === null ? '' : (this.postesSources().find((p) => p.id === id)?.libelle ?? '');
  });

  constructor() {
    this.chargerListes();
  }

  chargerListes(): void {
    this.listesErreur.set(false);
    const vers = (items: { id: number; libelle: string }[]): Option[] =>
      items.map(({ id, libelle }) => ({ id, libelle })).sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'));
    forkJoin({
      regions: this.geo.getRegions(),
      postes: this.reseau.listPostesSources({ page_size: 500 }).pipe(map((p) => p.items)),
      natures: this.referentiel
        .list('natures', { page_size: 100, type_reseau: 'distribution' })
        .pipe(map((p) => p.items)),
      // Causes distribution et communes (100 au plus, maximum de l'API)
      causes: this.referentiel
        .list('causes', { page_size: 100 })
        .pipe(map((p) => p.items.filter((c) => c.type_reseau !== 'transport' && c.is_active))),
    })
      .pipe(
        catchError(() => {
          this.listesErreur.set(true);
          return of(null);
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((listes) => {
        if (!listes) return;
        this.regions.set(vers(listes.regions.filter((r) => r.is_active)));
        this.chargerServices(listes.regions.filter((r) => r.is_active).map((r) => r.id));
        this.postesSources.set(vers(listes.postes.filter((p) => p.is_active)));
        this.natures.set(vers(listes.natures));
        this.causes.set(vers(listes.causes));
      });
  }

  /** Services de chaque région (pas de liste nationale dans l'API) ; un échec garde « n° … ». */
  private chargerServices(regionIds: number[]): void {
    if (!regionIds.length) return;
    forkJoin(regionIds.map((id) => this.geo.getServicesByRegion(id).pipe(catchError(() => of([])))))
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((parRegion) => {
        const uniques = new Map<number, Option>();
        for (const s of parRegion.flat()) uniques.set(s.id, { id: s.id, libelle: s.libelle });
        this.services.set([...uniques.values()].sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr')));
      });
  }

  choisirMode(mode: ModePeriode): void {
    this.personnalise.set(mode === 'personnalise');
    this.f.choisirMode(mode);
  }

  /** Date choisie : si elle croise l'autre borne, l'autre borne suit (période d'un jour). */
  changerDate(cle: 'debut' | 'fin', champ: HTMLInputElement): void {
    const valeur = champ.value;
    const { debut, fin } = this.f.filtres();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(valeur)) {
      champ.value = cle === 'debut' ? debut : fin;
      return;
    }
    const nouveau = { debut, fin, [cle]: valeur };
    if (nouveau.fin < nouveau.debut) {
      if (cle === 'debut') nouveau.fin = valeur;
      else nouveau.debut = valeur;
    }
    this.f.definir(nouveau);
  }

  changerEntier(cle: CleFiltre, valeur: string): void {
    const n = Number(valeur);
    this.f.definir({ [cle]: Number.isInteger(n) && n > 0 ? n : null });
  }

  changerReseau(valeur: string): void {
    this.f.definir({ reseau: valeur === 'hta' || valeur === 'htb' ? (valeur as ReseauCause) : null });
  }

  changerExogene(valeur: string): void {
    this.f.definir({ exogene: valeur === 'oui' ? true : valeur === 'non' ? false : null });
  }

  /** Poste source saisi dans le champ avec suggestions : retenu seulement s'il existe. */
  changerPosteSource(champ: HTMLInputElement): void {
    const t = champ.value.trim().toLowerCase();
    this.posteInconnu.set(false);
    if (!t) {
      this.f.definir({ poste_source_id: null });
      return;
    }
    const poste = this.postesSources().find((p) => p.libelle.toLowerCase() === t);
    if (poste) {
      this.f.definir({ poste_source_id: poste.id });
    } else {
      // Nom inconnu : on revient au poste appliqué et on le dit
      champ.value = this.posteSourceSaisi();
      this.posteInconnu.set(true);
    }
  }

  private libelleValeur(cle: CleFiltre, valeur: unknown): string {
    const parId = (liste: Option[]) => liste.find((o) => o.id === valeur)?.libelle ?? `n° ${valeur}`;
    switch (cle) {
      case 'region_id':
        return parId(this.regions());
      case 'service_id':
        return parId(this.services());
      case 'poste_source_id':
        return parId(this.postesSources());
      case 'nature_id':
        return parId(this.natures());
      case 'cause_id':
        return parId(this.causes());
      case 'reseau':
        return valeur === 'htb' ? 'HTB' : 'HTA';
      case 'exogene':
        return valeur ? 'oui' : 'non';
      default:
        return `n° ${valeur}`;
    }
  }
}
