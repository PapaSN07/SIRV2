import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { combineLatest, map } from 'rxjs';
import type { EChartsOption } from 'echarts';
import {
  CategorieNature,
  EvolutionSuivi,
  Granularite,
  PointEvolution,
} from '../../../shared/models/suivi-incidents.models';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { GraphiqueComponent } from '../../../shared/ui/graphique/graphique.component';
import { COULEUR_NATURE, COULEURS } from '../../../shared/ui/graphique/couleurs-metier';
import { formatDuree, formatEnd, formatEntier } from '../../../shared/utils/formats-indicateurs';
import { Etat, charger, filtresResolus$ } from '../services/chargement';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';

type ChoixGranularite = Granularite | 'auto';
type Mesure = 'nombre' | 'duree' | 'end';

const GRANULARITES: { cle: ChoixGranularite; libelle: string }[] = [
  { cle: 'auto', libelle: 'Automatique' },
  { cle: 'jour', libelle: 'Jour' },
  { cle: 'semaine', libelle: 'Semaine' },
  { cle: 'mois', libelle: 'Mois' },
];

const MESURES: { cle: Mesure; libelle: string }[] = [
  { cle: 'nombre', libelle: 'Nombre' },
  { cle: 'duree', libelle: 'Durée' },
  { cle: 'end', libelle: 'END' },
];

/** Ordre d'empilement : de bas en haut, comme la légende de la Vue d'ensemble. */
const NATURES: { cle: CategorieNature; libelle: string }[] = [
  { cle: 'incident', libelle: 'Incidents' },
  { cle: 'delestage', libelle: 'Délestages' },
  { cle: 'travaux', libelle: 'Travaux' },
  { cle: 'autre', libelle: 'Autres coupures' },
];

/** Au-delà, une série par jour devient illisible (l'API refuse aussi). */
const JOURS_MAX_PAR_JOUR = 366;

const LIBELLE_UNITE: Record<Granularite, string> = { jour: 'jour', semaine: 'semaine Senelec', mois: 'mois' };

/**
 * Onglet « Évolution » : interruptions par jour, semaine Senelec ou mois, empilées par nature.
 * Un clic sur une barre restreint la période du menu à cet intervalle.
 */
@Component({
  selector: 'sir-suivi-evolution',
  standalone: true,
  imports: [EtatComponent, GraphiqueComponent],
  templateUrl: './evolution.component.html',
  styleUrl: './evolution.component.scss',
})
export class EvolutionComponent {
  private readonly api = inject(SuiviIncidentsService);
  readonly f = inject(SuiviIncidentsFiltresService);

  readonly granularites = GRANULARITES;
  readonly mesures = MESURES;
  readonly natures = NATURES;
  readonly formatEntier = formatEntier;
  readonly formatDuree = formatDuree;
  readonly formatEnd = formatEnd;

  readonly granularite = signal<ChoixGranularite>('auto');
  readonly mesure = signal<Mesure>('nombre');
  readonly etat = signal<Etat<EvolutionSuivi>>({ type: 'chargement' });
  private readonly relance = signal(0);

  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  /** Nombre de jours de la période (fin incluse). */
  readonly joursPeriode = computed(() => {
    const { debut, fin } = this.f.effectifs();
    return Math.round((Date.parse(fin) - Date.parse(debut)) / 86_400_000) + 1;
  });

  readonly jourIndisponible = computed(() => this.joursPeriode() > JOURS_MAX_PAR_JOUR);

  /** Choix appliqué : « Jour » choisi puis période allongée au-delà d'un an → automatique. */
  readonly granulariteEffective = computed<ChoixGranularite>(() =>
    this.granularite() === 'jour' && this.jourIndisponible() ? 'auto' : this.granularite(),
  );

  constructor() {
    const granularite$ = toObservable(this.granulariteEffective);
    charger(
      combineLatest([filtresResolus$(this.filtresResolus), granularite$, toObservable(this.relance)]).pipe(
        map(([x, g]) => ({ x, g })),
      ),
      ({ x, g }) => this.api.getEvolution(x, g),
      (e) => this.etat.set(e),
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly donnees = computed(() => {
    const e = this.etat();
    return e.type === 'ok' ? e.donnees : null;
  });

  readonly vide = computed(() => (this.donnees()?.points ?? []).every((p) => p.nombre === 0));

  readonly uniteAppliquee = computed(() => {
    const d = this.donnees();
    return d ? LIBELLE_UNITE[d.granularite] : '';
  });

  readonly totaux = computed(() => {
    const points = this.donnees()?.points ?? [];
    return {
      nombre: points.reduce((s, p) => s + p.nombre, 0),
      duree: points.reduce((s, p) => s + p.duree_heures, 0),
      end: points.reduce((s, p) => s + p.end_mwh, 0),
      natures: Object.fromEntries(
        NATURES.map((n) => [n.cle, points.reduce((s, p) => s + p.natures[n.cle], 0)]),
      ) as Record<CategorieNature, number>,
    };
  });

  readonly options = computed<EChartsOption>(() => {
    const points = this.donnees()?.points ?? [];
    const mesure = this.mesure();
    const axe = { type: 'category' as const, data: points.map((p) => p.libelle), axisTick: { show: false }, axisLabel: { color: COULEURS.texteSecondaire, hideOverlap: true } };
    // END : kWh si toute la série est sous 1 MWh, sinon MWh ; graduations entières, unité en titre d'axe
    const enKwh = mesure === 'end' && points.every((p) => p.end_mwh < 1);
    const facteur = enKwh ? 1000 : 1;
    const unite = mesure === 'end' ? (enKwh ? 'kWh' : 'MWh') : mesure === 'duree' ? 'h' : '';
    const valeurs = {
      type: 'value' as const,
      name: unite,
      nameTextStyle: { color: COULEURS.texteSecondaire, align: 'left' as const },
      splitLine: { lineStyle: { color: COULEURS.grille } },
      axisLabel: { color: COULEURS.texteSecondaire, formatter: (v: number) => formatEntier(v) },
    };
    const infobulle = {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (params: unknown) => {
        const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0;
        const p = points[i];
        if (!p) return '';
        const lignes = NATURES.filter((n) => p.natures[n.cle] > 0).map(
          (n) =>
            `<span style="display:inline-block;width:10px;height:10px;margin-right:4px;border:1px solid #fff;border-radius:2px;background:${COULEUR_NATURE[n.cle]}"></span>${n.libelle} : ${formatEntier(p.natures[n.cle])}`,
        );
        return [
          `<strong>${this.intervalle(p)}</strong>`,
          `${formatEntier(p.nombre)} interruptions`,
          ...lignes,
          `Durée : ${formatDuree(p.duree_heures)}`,
          `END : ${formatEnd(p.end_mwh)}`,
        ].join('<br>');
      },
    };
    const grille = { left: 8, right: 8, top: 36, bottom: 8, containLabel: true };
    if (mesure === 'nombre') {
      return {
        grid: grille,
        tooltip: infobulle,
        legend: { show: true, type: 'scroll' },
        xAxis: axe,
        yAxis: valeurs,
        series: NATURES.map((n) => ({
          type: 'bar' as const,
          name: n.libelle,
          stack: 'empilement',
          barMaxWidth: 36,
          itemStyle: { color: COULEUR_NATURE[n.cle] },
          emphasis: { focus: 'series' as const },
          data: points.map((p) => p.natures[n.cle]),
        })),
      };
    }
    return {
      grid: grille,
      tooltip: infobulle,
      legend: { show: false },
      xAxis: axe,
      yAxis: valeurs,
      series: [
        {
          type: 'bar',
          name: mesure === 'duree' ? 'Durée (h)' : 'END (MWh)',
          barMaxWidth: 36,
          itemStyle: { color: COULEURS.violet, borderRadius: [3, 3, 0, 0] },
          data: points.map((p) => (mesure === 'duree' ? p.duree_heures : p.end_mwh * facteur)),
        },
      ],
    };
  });

  readonly resume = computed(() => {
    const d = this.donnees();
    if (!d || !d.points.length) return '';
    const max = d.points.reduce((a, b) => (b.nombre > a.nombre ? b : a));
    const t = this.totaux();
    return `${formatEntier(t.nombre)} interruptions sur ${d.points.length} ${this.uniteAppliquee()}${d.points.length > 1 ? 's' : ''} ; maximum ${formatEntier(max.nombre)} (${this.intervalle(max)}).`;
  });

  /** « 14/11/2026 » ou « 14/11 → 20/11/2026 ». */
  intervalle(p: PointEvolution): string {
    const court = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
    const long = (iso: string) => `${court(iso)}/${iso.slice(0, 4)}`;
    return p.debut === p.fin ? long(p.debut) : `${court(p.debut)} → ${long(p.fin)}`;
  }

  readonly choisirGranularite = (g: ChoixGranularite): void => {
    if (g === 'jour' && this.jourIndisponible()) return;
    this.granularite.set(g);
  };

  readonly choisirMesure = (m: Mesure): void => {
    this.mesure.set(m);
  };

  /** Flèches dans un groupe radio : passe au choix voisin disponible et y met le focus. */
  naviguer<T extends string>(evenement: KeyboardEvent, choix: { cle: T }[], courant: T, choisir: (c: T) => void, desactive: (c: T) => boolean = () => false): void {
    const pas = ['ArrowRight', 'ArrowDown'].includes(evenement.key) ? 1 : ['ArrowLeft', 'ArrowUp'].includes(evenement.key) ? -1 : 0;
    if (!pas) return;
    evenement.preventDefault();
    let i = choix.findIndex((c) => c.cle === courant);
    for (let n = 0; n < choix.length; n++) {
      i = (i + pas + choix.length) % choix.length;
      if (!desactive(choix[i].cle)) break;
    }
    choisir(choix[i].cle);
    (evenement.currentTarget as HTMLElement | null)?.querySelectorAll<HTMLElement>('button')[i]?.focus();
  }

  readonly estJourDesactive = (c: ChoixGranularite): boolean => c === 'jour' && this.jourIndisponible();

  /** Clic sur une barre : la période du menu devient cet intervalle (pastille de période, Précédent annule). */
  /** Le tableau des données propose le même zoom que le clic sur une barre (clavier). */
  zoomerLigne(index: number): void {
    const p = this.donnees()?.points[index];
    if (p) this.zoomer({ nom: p.libelle, index });
  }

  zoomer(evenement: { nom: string; index: number | null }): void {
    // Par l'index : un libellé (« 14/11 », « S47 ») peut revenir sur une période de plus d'un an
    const p = evenement.index === null ? undefined : this.donnees()?.points[evenement.index];
    if (!p || (p.debut === this.f.effectifs().debut && p.fin === this.f.effectifs().fin)) return;
    this.f.definir({ debut: p.debut, fin: p.fin });
  }

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }
}
