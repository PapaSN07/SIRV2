import { Component, computed, input, output } from '@angular/core';
import { NgxEchartsDirective, provideEchartsCore } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { COULEURS, PALETTE } from './couleurs-metier';

/** Base commune : police Inter, couleurs de la charte, description ARIA (module aria d'ECharts). */
const BASE: EChartsOption = {
  color: PALETTE,
  textStyle: { fontFamily: 'Inter, sans-serif', color: COULEURS.texte, fontSize: 12 },
  aria: { enabled: true },
  grid: { left: 8, right: 8, top: 32, bottom: 8, containLabel: true },
  legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 12, textStyle: { color: COULEURS.texteSecondaire } },
  tooltip: {
    trigger: 'axis',
    confine: true,
    backgroundColor: COULEURS.navy,
    borderWidth: 0,
    textStyle: { color: '#fff', fontSize: 12 },
  },
  animationDuration: 300,
};

/**
 * Enveloppe des graphiques ECharts aux couleurs de la charte.
 *
 * Le parent fournit l'option propre au graphique (séries, axes) ; la base est fusionnée
 * dessous. Un clic sur un élément remonte `{nom, serie, valeur}` (filtre par clic).
 * Toujours accompagné d'un titre et d'un résumé textuel (`resume`) pour les lecteurs d'écran.
 */
function isObjet(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

@Component({
  selector: 'sir-graphique',
  standalone: true,
  imports: [NgxEchartsDirective],
  providers: [provideEchartsCore({ echarts: () => import('./echarts-sir').then((m) => m.default) })],
  template: `
    <figure class="graphique" [attr.aria-label]="titre()">
      <div
        echarts
        class="graphique__zone"
        [style.height]="hauteur()"
        [options]="optionsCompletes()"
        [autoResize]="true"
        (chartClick)="surClic($event)"
      ></div>
      @if (resume()) {
        <figcaption class="graphique__resume">{{ resume() }}</figcaption>
      }
    </figure>
  `,
  styles: `
    .graphique { margin: 0; min-width: 0; }
    .graphique__zone { width: 100%; }
    .graphique__resume { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  `,
})
export class GraphiqueComponent {
  readonly options = input.required<EChartsOption>();
  readonly titre = input.required<string>();
  /** Phrase résumant ce que montre le graphique (lecteurs d'écran). */
  readonly resume = input<string | null>(null);
  readonly hauteur = input('280px');
  readonly clic = output<{ nom: string; serie: string | null; valeur: unknown; index: number | null }>();

  /** Fusion à deux niveaux : un graphique qui précise `tooltip.trigger` garde le style de base. */
  readonly optionsCompletes = computed<EChartsOption>(() => {
    const options = this.options() as Record<string, unknown>;
    const base = BASE as Record<string, unknown>;
    const fusion: Record<string, unknown> = { ...base, ...options };
    for (const cle of ['tooltip', 'legend', 'grid', 'textStyle']) {
      const b = base[cle];
      const o = options[cle];
      if (isObjet(b) && isObjet(o)) fusion[cle] = { ...b, ...o };
    }
    return fusion as EChartsOption;
  });

  surClic(evenement: { name?: string; seriesName?: string; value?: unknown; dataIndex?: number }): void {
    if (!evenement.name) return;
    this.clic.emit({
      nom: evenement.name,
      serie: evenement.seriesName ?? null,
      valeur: evenement.value,
      index: evenement.dataIndex ?? null,
    });
  }
}
