import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, combineLatest, distinctUntilChanged, filter, map, of, switchMap, tap } from 'rxjs';
import type { EChartsOption } from 'echarts';
import {
  ClassementSuivi,
  FiltresIncidents,
  LigneClassement,
  NiveauClassement,
  VueEnsemble,
} from '../../../shared/models/suivi-incidents.models';
import { KpiComponent } from '../../../shared/ui/kpi/kpi.component';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { GraphiqueComponent } from '../../../shared/ui/graphique/graphique.component';
import { COULEUR_NATURE, COULEURS } from '../../../shared/ui/graphique/couleurs-metier';
import {
  formatDuree,
  formatEnd,
  formatEndParties,
  formatEntier,
  formatPart,
} from '../../../shared/utils/formats-indicateurs';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';

type Etat<T> = { type: 'chargement' } | { type: 'erreur'; message: string } | { type: 'ok'; donnees: T };

const NIVEAUX: { cle: NiveauClassement; libelle: string; filtre: keyof FiltresIncidents }[] = [
  { cle: 'service', libelle: 'Service', filtre: 'service_id' },
  { cle: 'poste_source', libelle: 'Poste source', filtre: 'poste_source_id' },
  { cle: 'feeder', libelle: 'Feeder', filtre: 'feeder_id' },
];

const LIBELLE_RESEAU = { hta: 'HTA', htb: 'HTB', total: 'Total' } as const;

const memes = <T>(a: T, b: T): boolean => JSON.stringify(a) === JSON.stringify(b);

function messageErreur(err: unknown): string {
  if (err instanceof HttpErrorResponse && err.status === 403) {
    return 'Ces données sont hors de votre périmètre.';
  }
  if (err instanceof HttpErrorResponse && (err.status === 0 || err.status >= 500)) {
    return 'Les indicateurs n’ont pas pu être chargés (serveur indisponible). Réessayez dans un instant.';
  }
  const m = (err as { message?: unknown } | null)?.message;
  return typeof m === 'string' && m ? m : 'Les données n’ont pas pu être chargées.';
}

/** Charge une ressource à chaque changement de clé ; « Réessayer » relance la dernière. */
function charger<K, T>(cle$: Observable<K>, appel: (cle: K) => Observable<T>, cible: (e: Etat<T>) => void): Observable<unknown> {
  return cle$.pipe(
    tap(() => cible({ type: 'chargement' })),
    switchMap((cle) =>
      appel(cle).pipe(
        map((donnees) => cible({ type: 'ok', donnees })),
        catchError((err: unknown) => of(cible({ type: 'erreur', message: messageErreur(err) }))),
      ),
    ),
  );
}

/**
 * Onglet « Vue d'ensemble » : indicateurs clés avec l'écart à la période précédente,
 * répartition par nature, END HTA / HTB, classement territorial (un clic filtre le menu).
 */
@Component({
  selector: 'sir-suivi-vue-ensemble',
  standalone: true,
  imports: [KpiComponent, EtatComponent, GraphiqueComponent],
  templateUrl: './vue-ensemble.component.html',
  styleUrl: './vue-ensemble.component.scss',
})
export class VueEnsembleComponent {
  private readonly api = inject(SuiviIncidentsService);
  readonly f = inject(SuiviIncidentsFiltresService);

  readonly niveaux = NIVEAUX;
  readonly libelleReseau = LIBELLE_RESEAU;
  readonly formatEntier = formatEntier;
  readonly formatEnd = formatEnd;
  readonly formatEndParties = formatEndParties;
  readonly formatDuree = formatDuree;
  readonly formatPart = formatPart;

  readonly vue = signal<Etat<VueEnsemble>>({ type: 'chargement' });
  readonly classement = signal<Etat<ClassementSuivi>>({ type: 'chargement' });
  readonly niveau = signal<NiveauClassement>('service');
  private readonly relance = signal(0);
  private readonly relanceClassement = signal(0);

  /** Filtres résolus par l'API (périmètre imposé compris) : on attend la résolution. */
  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  constructor() {
    const filtres$ = toObservable(this.filtresResolus).pipe(
      filter((x): x is FiltresIncidents => x !== null),
      distinctUntilChanged<FiltresIncidents>(memes),
    );

    charger(
      combineLatest([filtres$, toObservable(this.relance)]).pipe(map(([x]) => x)),
      (x) => this.api.getVueEnsemble(x),
      (e) => this.vue.set(e),
    )
      .pipe(takeUntilDestroyed())
      .subscribe();

    charger(
      combineLatest([filtres$, toObservable(this.niveau), toObservable(this.relanceClassement)]).pipe(
        map(([x, n]) => ({ x, n })),
      ),
      ({ x, n }) => this.api.getClassement(x, n),
      (e) => this.classement.set(e),
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly donnees = computed(() => {
    const v = this.vue();
    return v.type === 'ok' ? v.donnees : null;
  });

  readonly vide = computed(() => this.donnees()?.kpi.nombre_interruptions === 0);

  readonly libellePrecedent = computed(() => this.donnees()?.periode_precedente.libelle ?? '');

  /** Barres horizontales par nature : nombre d'interruptions, couleur métier, valeur écrite. */
  readonly optionsNatures = computed<EChartsOption>(() => {
    const natures = this.donnees()?.natures ?? [];
    const lignes = [...natures].reverse();
    return {
      grid: { left: 8, right: 48, top: 8, bottom: 8, containLabel: true },
      legend: { show: false },
      tooltip: {
        trigger: 'item',
        formatter: (p: unknown) => {
          const i = (p as { dataIndex: number }).dataIndex;
          const n = lignes[i];
          return `<strong>${n.libelle}</strong><br>${formatEntier(n.nombre)} interruptions (${formatPart(n.part)})<br>Durée : ${formatDuree(n.duree_heures)}<br>END : ${formatEnd(n.end_mwh)}`;
        },
      },
      xAxis: { type: 'value', show: false },
      yAxis: {
        type: 'category',
        data: lignes.map((n) => n.libelle),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: COULEURS.texte, fontSize: 13 },
      },
      series: [
        {
          type: 'bar',
          name: 'Interruptions',
          barMaxWidth: 26,
          data: lignes.map((n) => ({ value: n.nombre, itemStyle: { color: COULEUR_NATURE[n.categorie], borderRadius: [0, 4, 4, 0] } })),
          label: { show: true, position: 'right', color: COULEURS.texte, formatter: (p: unknown) => formatEntier((p as { value: number }).value) },
        },
      ],
    };
  });

  readonly resumeNatures = computed(() =>
    (this.donnees()?.natures ?? []).map((n) => `${n.libelle} : ${formatEntier(n.nombre)} (${formatPart(n.part)})`).join(' ; '),
  );

  readonly lignesClassement = computed<LigneClassement[]>(() => {
    const c = this.classement();
    return c.type === 'ok' ? c.donnees.lignes : [];
  });

  readonly autresClassement = computed(() => {
    const c = this.classement();
    return c.type === 'ok' ? c.donnees.autres : null;
  });

  /** Plus grand nombre du classement (barre de proportion dans le tableau). */
  readonly maxClassement = computed(() => Math.max(1, ...this.lignesClassement().map((l) => l.nombre)));

  readonly niveauCourant = computed(() => NIVEAUX.find((n) => n.cle === this.niveau())!);

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }

  reessayerClassement(): void {
    this.relanceClassement.update((n) => n + 1);
  }

  choisirNiveau(n: NiveauClassement): void {
    this.niveau.set(n);
  }

  /** Flèches gauche / droite entre les niveaux (groupe de boutons à choix unique). */
  naviguerNiveau(evenement: KeyboardEvent): void {
    const i = NIVEAUX.findIndex((n) => n.cle === this.niveau());
    const pas = ['ArrowRight', 'ArrowDown'].includes(evenement.key) ? 1 : ['ArrowLeft', 'ArrowUp'].includes(evenement.key) ? -1 : 0;
    if (!pas) return;
    evenement.preventDefault();
    const suivant = NIVEAUX[(i + pas + NIVEAUX.length) % NIVEAUX.length];
    this.niveau.set(suivant.cle);
    const groupe = (evenement.currentTarget as HTMLElement | null)?.querySelectorAll<HTMLElement>('button');
    groupe?.[NIVEAUX.indexOf(suivant)]?.focus();
  }

  /** Un clic sur une ligne du classement devient un filtre du menu (pastille annulable). */
  filtrerSur(ligne: LigneClassement): void {
    if (ligne.id === null) return;
    this.f.definir({ [this.niveauCourant().filtre]: ligne.id } as Partial<FiltresIncidents>);
    // Le tableau se recharge : le focus va au titre du bloc plutôt que de retomber sur la page
    document.getElementById('titre-classement')?.focus();
  }
}
