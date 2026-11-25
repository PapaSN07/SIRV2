import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { catchError, debounceTime, distinctUntilChanged, of, switchMap, tap } from 'rxjs';
import {
  FiltresIncidents,
  FiltresResolus,
  ModePeriode,
  ReseauCause,
} from '../../../shared/models/suivi-incidents.models';
import {
  ajouterJours,
  aujourdhuiIso,
  semaineSenelec,
  semaineSenelecPassee,
} from '../../../shared/utils/semaine-senelec';
import { SuiviIncidentsService } from './suivi-incidents.service';

/** Filtres autres que la période, dans l'ordre des pastilles. */
export const CLES_FILTRES = [
  'region_id',
  'service_id',
  'poste_source_id',
  'feeder_id',
  'nature_id',
  'cause_id',
  'reseau',
  'exogene',
] as const;
export type CleFiltre = (typeof CLES_FILTRES)[number];

/** Nom court des paramètres dans l'URL (lien partageable lisible). */
const PARAM_URL: Record<CleFiltre | 'debut' | 'fin', string> = {
  debut: 'du',
  fin: 'au',
  region_id: 'region',
  service_id: 'service',
  poste_source_id: 'poste_source',
  feeder_id: 'feeder',
  nature_id: 'nature',
  cause_id: 'cause',
  reseau: 'reseau',
  exogene: 'exogene',
};

const meme = <T>(a: T, b: T): boolean => JSON.stringify(a) === JSON.stringify(b);

/**
 * État des filtres du menu « Suivi incidents », partagé par tous ses onglets.
 *
 * Fourni par le composant parent (une instance par visite du menu). L'URL est la source :
 * un lien copié, un F5 ou les boutons Précédent / Suivant redonnent le même écran. Sans
 * période dans l'URL (première visite), c'est la dernière semaine Senelec terminée ; dès que
 * l'utilisateur agit, la période est écrite pour qu'un lien partagé garde son sens.
 *
 * Chaque changement demande à l'API les filtres complétés (périmètre imposé par le rôle,
 * libellé). Les onglets doivent lire `effectifs()` (région / service imposés compris).
 * Un 403 (lien vers une région ou un service hors périmètre) retire ces filtres et relance.
 */
@Injectable()
export class SuiviIncidentsFiltresService {
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(SuiviIncidentsService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly _filtres = signal<FiltresIncidents>(lireUrl(this.route.snapshot.queryParams));

  /** Filtres demandés (URL), avant réponse de l'API. */
  readonly filtres = this._filtres.asReadonly();
  /** Réponse de l'API pour les filtres demandés. */
  readonly resolus = signal<FiltresResolus | null>(null);
  readonly erreur = signal<string | null>(null);
  /** Information non bloquante (ex. filtre hors périmètre retiré). */
  readonly avertissement = signal<string | null>(null);
  readonly chargement = signal(false);
  /** Libellés transmis par l'onglet qui pose un filtre (clic dans un classement, sur la carte). */
  private readonly libelles = signal<Map<string, string>>(new Map());

  /** Filtres à appliquer dans les onglets : ceux de l'API (région / service imposés), sinon ceux demandés. */
  readonly effectifs = computed<FiltresIncidents>(() => this.resolus()?.filtres ?? this._filtres());

  readonly mode = computed<ModePeriode>(() => modePeriode(this._filtres().debut, this._filtres().fin));

  /** Filtres renseignés hors période (pastilles), région / service imposés compris. */
  readonly actifs = computed(() =>
    CLES_FILTRES.filter((cle) => this.effectifs()[cle] !== null).map((cle) => ({ cle, valeur: this.effectifs()[cle] })),
  );

  readonly regionVerrouillee = computed(() => this.resolus()?.perimetre.region_verrouillee ?? false);
  readonly serviceVerrouille = computed(() => this.resolus()?.perimetre.service_verrouille ?? false);

  /** Filtres que « Tout effacer » retire vraiment (hors région / service imposés par le rôle). */
  readonly effacables = computed(() =>
    this.actifs().filter(
      (a) => !(a.cle === 'region_id' && this.regionVerrouillee()) && !(a.cle === 'service_id' && this.serviceVerrouille()),
    ),
  );

  /** La période suivante commencerait après aujourd'hui. */
  readonly finAtteinte = computed(() => this._filtres().fin >= aujourdhuiIso());

  constructor() {
    // URL → état : Précédent / Suivant, lien interne vers le menu sans paramètres.
    this.route.queryParams.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const lus = lireUrl(params);
      if (!meme(lus, this._filtres())) this._filtres.set(lus);
    });

    // État → API (filtres complétés et périmètre).
    toObservable(this._filtres)
      .pipe(
        debounceTime(150),
        distinctUntilChanged(meme),
        tap(() => {
          this.chargement.set(true);
          this.erreur.set(null);
        }),
        switchMap((f) =>
          this.api.getFiltres(f).pipe(
            catchError((err: unknown) => {
              this.traiterErreur(f, err);
              return of(null);
            }),
          ),
        ),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((resolus) => {
        this.chargement.set(false);
        if (resolus) this.resolus.set(resolus);
      });
  }

  /** Libellé d'une valeur de filtre transmis par un onglet, sinon null (la barre cherche dans ses listes). */
  libelleConnu(cle: CleFiltre, valeur: unknown): string | null {
    return this.libelles().get(`${cle}:${valeur}`) ?? null;
  }

  /**
   * Modifie un ou plusieurs filtres et met l'URL à jour (nouvelle entrée d'historique : Précédent annule).
   * `libelle` : nom de la valeur posée, pour la pastille (feeder, service… choisis depuis un onglet).
   */
  definir(modif: Partial<FiltresIncidents>, libelle?: string | null): void {
    if (libelle) {
      const [cle, valeur] = Object.entries(modif)[0] ?? [];
      if (cle !== undefined && valeur !== null && valeur !== undefined) {
        this.libelles.update((m) => new Map(m).set(`${cle}:${valeur}`, libelle));
      }
    }
    this.avertissement.set(null);
    this._filtres.update((f) => ({ ...f, ...modif }));
    this.ecrireUrl();
  }

  effacer(cle: CleFiltre): void {
    this.definir({ [cle]: null } as Partial<FiltresIncidents>);
  }

  /** Retire tous les filtres hors période (le périmètre imposé par le rôle reste appliqué par l'API). */
  toutEffacer(): void {
    const vide = Object.fromEntries(CLES_FILTRES.map((cle) => [cle, null])) as Partial<FiltresIncidents>;
    this.definir(vide);
  }

  /** Raccourci de période ; Mois et Année partent du dernier jour de la période affichée. */
  choisirMode(mode: ModePeriode): void {
    if (mode === 'personnalise') return;
    this.definir(bornesMode(mode, this._filtres().fin));
  }

  /** Période précédente (−1) ou suivante (+1) de même nature. */
  decaler(sens: -1 | 1): void {
    const { debut, fin } = this._filtres();
    const mode = this.mode();
    if (mode === 'semaine') {
      this.definir({ debut: ajouterJours(debut, 7 * sens), fin: ajouterJours(fin, 7 * sens) });
    } else if (mode === 'mois') {
      const [a, m] = debut.split('-').map(Number);
      const cible = new Date(Date.UTC(a, m - 1 + sens, 1)).toISOString().slice(0, 10);
      this.definir(bornesMode('mois', cible));
    } else if (mode === 'annee') {
      this.definir(bornesMode('annee', `${Number(debut.slice(0, 4)) + sens}-01-01`));
    } else {
      const jours = Math.round((Date.parse(fin) - Date.parse(debut)) / 86_400_000) + 1;
      this.definir({ debut: ajouterJours(debut, jours * sens), fin: ajouterJours(fin, jours * sens) });
    }
  }

  private traiterErreur(f: FiltresIncidents, err: unknown): void {
    const statut = err instanceof HttpErrorResponse ? err.status : null;
    if (statut === 403 && (f.region_id !== null || f.service_id !== null)) {
      // Lien vers une région / un service hors périmètre : on garde le reste des filtres.
      this.definir({ region_id: null, service_id: null });
      this.avertissement.set('La région ou le service du lien sont hors de votre périmètre : filtre retiré.');
      return;
    }
    const message = (err as { message?: unknown } | null)?.message;
    this.erreur.set(typeof message === 'string' && message ? message : 'Les filtres n’ont pas pu être appliqués.');
  }

  private ecrireUrl(): void {
    const f = this._filtres();
    const queryParams: Params = { [PARAM_URL.debut]: f.debut, [PARAM_URL.fin]: f.fin };
    for (const cle of CLES_FILTRES) {
      const v = f[cle];
      queryParams[PARAM_URL[cle]] = v === null ? null : typeof v === 'boolean' ? (v ? 'oui' : 'non') : v;
    }
    void this.router.navigate([], { relativeTo: this.route, queryParams, queryParamsHandling: 'merge' });
  }
}

/** Date « AAAA-MM-JJ » réelle (refuse 2026-02-31). */
function dateValide(v: unknown): v is string {
  if (typeof v !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(v)) return false;
  const [a, m, j] = v.split('-').map(Number);
  const d = new Date(Date.UTC(a, m - 1, j));
  return d.getUTCFullYear() === a && d.getUTCMonth() === m - 1 && d.getUTCDate() === j;
}

/** Filtres d'après l'URL ; période absente ou illisible → dernière semaine Senelec terminée. */
export function lireUrl(params: Params): FiltresIncidents {
  const entier = (cle: CleFiltre): number | null => {
    const n = Number(params[PARAM_URL[cle]]);
    return Number.isInteger(n) && n > 0 ? n : null;
  };
  let debut: string = params[PARAM_URL.debut];
  let fin: string = params[PARAM_URL.fin];
  if (!dateValide(debut) || !dateValide(fin) || fin < debut) {
    const defaut = semaineSenelecPassee(aujourdhuiIso());
    debut = defaut.debut;
    fin = defaut.fin;
  }
  const reseau = params[PARAM_URL.reseau];
  const exogene = params[PARAM_URL.exogene];
  return {
    debut,
    fin,
    region_id: entier('region_id'),
    service_id: entier('service_id'),
    poste_source_id: entier('poste_source_id'),
    feeder_id: entier('feeder_id'),
    nature_id: entier('nature_id'),
    cause_id: entier('cause_id'),
    reseau: reseau === 'hta' || reseau === 'htb' ? (reseau as ReseauCause) : null,
    exogene: exogene === 'oui' ? true : exogene === 'non' ? false : null,
  };
}

/** Nature de la période : semaine Senelec, mois civil, année civile, ou personnalisée. */
export function modePeriode(debut: string, fin: string): ModePeriode {
  const s = semaineSenelec(debut);
  if (s.debut === debut && s.fin === fin) return 'semaine';
  if (debut.endsWith('-01-01') && fin === `${debut.slice(0, 4)}-12-31`) return 'annee';
  if (debut.endsWith('-01') && fin === finDeMois(debut)) return 'mois';
  return 'personnalise';
}

/**
 * Bornes d'un raccourci autour du jour `reference` : sa semaine Senelec (ou la dernière
 * terminée si elle est en cours), son mois, son année.
 */
export function bornesMode(mode: Exclude<ModePeriode, 'personnalise'>, reference: string | null): { debut: string; fin: string } {
  const ref = reference ?? aujourdhuiIso();
  if (mode === 'semaine') {
    const aujourdhui = aujourdhuiIso();
    const s = semaineSenelec(ref);
    const terminee = s.fin < aujourdhui ? s : semaineSenelecPassee(aujourdhui);
    return { debut: terminee.debut, fin: terminee.fin };
  }
  if (mode === 'annee') return { debut: `${ref.slice(0, 4)}-01-01`, fin: `${ref.slice(0, 4)}-12-31` };
  const debut = `${ref.slice(0, 7)}-01`;
  return { debut, fin: finDeMois(debut) };
}

function finDeMois(premierJour: string): string {
  const [a, m] = premierJour.split('-').map(Number);
  return new Date(Date.UTC(a, m, 0)).toISOString().slice(0, 10);
}
