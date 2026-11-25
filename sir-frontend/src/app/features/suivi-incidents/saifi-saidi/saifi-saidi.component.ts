import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { combineLatest, map } from 'rxjs';
import type { EChartsOption } from 'echarts';
import { SaifiSaidiSuivi, SaifiService } from '../../../shared/models/suivi-incidents.models';
import { KpiComponent } from '../../../shared/ui/kpi/kpi.component';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { GraphiqueComponent } from '../../../shared/ui/graphique/graphique.component';
import { COULEUR_NATURE, COULEURS } from '../../../shared/ui/graphique/couleurs-metier';
import {
  formatDuree,
  formatEntier,
  formatPart,
  formatSaidi,
  formatSaifi,
} from '../../../shared/utils/formats-indicateurs';
import { Etat, charger, filtresResolus$ } from '../services/chargement';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';

type Indicateur = 'saifi' | 'saidi';

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const LIBELLE_RESEAU = { hta: 'HTA', htb: 'HTB', total: 'Total' } as const;
/** Graduations des axes : séparateurs français (« 0,5 »). */
const GRADUATION = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 });

/**
 * Onglet « SAIFI / SAIDI » : synthèse du périmètre (ou contribution des interruptions
 * filtrées), HTA / HTB, évolution mensuelle et cumul, détail par nature et par service.
 */
@Component({
  selector: 'sir-suivi-saifi-saidi',
  standalone: true,
  imports: [KpiComponent, EtatComponent, GraphiqueComponent],
  templateUrl: './saifi-saidi.component.html',
  styleUrl: './saifi-saidi.component.scss',
})
export class SaifiSaidiComponent {
  private readonly api = inject(SuiviIncidentsService);
  readonly f = inject(SuiviIncidentsFiltresService);

  readonly formatSaifi = formatSaifi;
  readonly formatSaidi = formatSaidi;
  readonly formatDuree = formatDuree;
  readonly formatEntier = formatEntier;
  readonly formatPart = formatPart;
  readonly libelleReseau = LIBELLE_RESEAU;
  readonly couleurNature = COULEUR_NATURE;

  readonly etat = signal<Etat<SaifiSaidiSuivi>>({ type: 'chargement' });
  readonly indicateur = signal<Indicateur>('saifi');
  private readonly relance = signal(0);

  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  constructor() {
    charger(
      combineLatest([filtresResolus$(this.filtresResolus), toObservable(this.relance)]).pipe(map(([x]) => x)),
      (x) => this.api.getSaifiSaidi(x),
      (e) => this.etat.set(e),
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly donnees = computed(() => {
    const e = this.etat();
    return e.type === 'ok' ? e.donnees : null;
  });

  readonly vide = computed(() => this.donnees()?.synthese.interruptions === 0);

  /** Interruptions comptées mais aucune base clients : SAIFI / SAIDI non calculables (pas « 0 »). */
  readonly sansBase = computed(() => {
    const s = this.donnees()?.synthese;
    return !!s && s.clients_reference === 0 && s.interruptions > 0;
  });

  /** SAIFI / SAIDI affichés, ou un tiret quand la base clients manque. */
  saifi(v: number): string {
    return this.sansBase() ? '—' : formatSaifi(v);
  }

  saidi(v: number): string {
    return this.sansBase() ? '—' : formatSaidi(v);
  }

  /** « Dakar », « national », « service SDDV »… : périmètre du dénominateur. */
  readonly perimetre = computed(() => {
    const p = this.f.resolus()?.perimetre;
    if (!p || p.niveau === 'national') return 'national';
    return p.niveau === 'region' ? 'de la région' : 'du service';
  });

  readonly moisReference = computed(() => {
    const m = this.donnees()?.mois_reference;
    return m ? `${MOIS[m.mois - 1]} ${m.annee}` : null;
  });

  readonly plusieursMois = computed(() => (this.donnees()?.mensuel.length ?? 0) > 1);

  readonly optionsMensuel = computed<EChartsOption>(() => {
    const mensuel = this.donnees()?.mensuel ?? [];
    const ind = this.indicateur();
    const fmt = (v: number) => (ind === 'saifi' ? formatSaifi(v) : formatSaidi(v));
    return {
      grid: { left: 8, right: 8, top: 56, bottom: 8, containLabel: true },
      legend: { show: true, type: 'scroll', top: 0 },
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const i = (params as { dataIndex: number }[])[0]?.dataIndex ?? 0;
          const m = mensuel[i];
          if (!m) return '';
          const val = ind === 'saifi' ? m.saifi : m.saidi;
          const cumul = ind === 'saifi' ? m.saifi_cumule : m.saidi_cumule;
          return `<strong>${m.libelle}</strong><br>Mois : ${fmt(val)}<br>Cumul : ${fmt(cumul)}<br>${formatEntier(m.interruptions)} interruptions comptées`;
        },
      },
      xAxis: { type: 'category', data: mensuel.map((m) => m.libelle), axisTick: { show: false }, axisLabel: { color: COULEURS.texteSecondaire, hideOverlap: true } },
      // Mois à gauche, cumul à droite : les barres mensuelles restent lisibles à côté d'un cumul annuel
      yAxis: [
        {
          type: 'value',
          name: ind === 'saidi' ? 'Mois (h)' : 'Mois',
          nameGap: 12,
          nameTextStyle: { color: COULEURS.texteSecondaire, align: 'left' },
          splitLine: { lineStyle: { color: COULEURS.grille } },
          axisLabel: { color: COULEURS.texteSecondaire, formatter: (v: number) => GRADUATION.format(v) },
        },
        {
          type: 'value',
          name: ind === 'saidi' ? 'Cumul (h)' : 'Cumul',
          nameGap: 12,
          nameTextStyle: { color: COULEURS.magenta, align: 'right' },
          splitLine: { show: false },
          axisLabel: { color: COULEURS.magenta, formatter: (v: number) => GRADUATION.format(v) },
        },
      ],
      series: [
        {
          type: 'bar',
          name: ind === 'saifi' ? 'SAIFI du mois' : 'SAIDI du mois',
          barMaxWidth: 36,
          itemStyle: { color: COULEURS.violet, borderRadius: [3, 3, 0, 0] },
          data: mensuel.map((m) => (ind === 'saifi' ? m.saifi : m.saidi)),
        },
        {
          type: 'line',
          name: `Cumul depuis ${mensuel[0]?.libelle ?? 'le début'}`,
          yAxisIndex: 1,
          symbolSize: 6,
          lineStyle: { width: 2 },
          itemStyle: { color: COULEURS.magenta },
          data: mensuel.map((m) => (ind === 'saifi' ? m.saifi_cumule : m.saidi_cumule)),
        },
      ],
    };
  });

  readonly resumeMensuel = computed(() => {
    const mensuel = this.donnees()?.mensuel ?? [];
    const ind = this.indicateur();
    const dernier = mensuel[mensuel.length - 1];
    if (!dernier) return '';
    const fmt = (v: number) => (ind === 'saifi' ? formatSaifi(v) : formatSaidi(v));
    return `${ind.toUpperCase()} par mois sur ${mensuel.length} mois ; cumul à fin ${dernier.libelle} : ${fmt(ind === 'saifi' ? dernier.saifi_cumule : dernier.saidi_cumule)}.`;
  });

  choisirIndicateur(i: Indicateur): void {
    this.indicateur.set(i);
  }

  naviguerIndicateur(evenement: KeyboardEvent): void {
    if (!['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp'].includes(evenement.key)) return;
    evenement.preventDefault();
    const suivant: Indicateur = this.indicateur() === 'saifi' ? 'saidi' : 'saifi';
    this.indicateur.set(suivant);
    (evenement.currentTarget as HTMLElement | null)
      ?.querySelectorAll<HTMLElement>('button')
      [suivant === 'saifi' ? 0 : 1]?.focus();
  }

  filtrerService(s: SaifiService): void {
    if (s.id === null || this.f.serviceVerrouille()) return;
    this.f.definir({ service_id: s.id });
    // La pastille du filtre apparaît en haut : on y ramène la vue
    document.getElementById('suivi-filtres')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }
}
