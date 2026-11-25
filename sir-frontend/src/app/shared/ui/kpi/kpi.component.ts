import { Component, computed, input } from '@angular/core';
import { ecartRelatif, formatEcart } from '../../utils/formats-indicateurs';

/**
 * Carte d'indicateur : libellé, valeur déjà formatée, unité, écart avec la période précédente.
 *
 * `sensFavorable` dit si une hausse est une bonne nouvelle (« hausse ») ou non (« baisse » :
 * nombre d'interruptions, SAIFI…) ; l'écart est coloré en conséquence et toujours écrit en
 * clair (pas d'information portée par la couleur seule).
 */
@Component({
  selector: 'sir-kpi',
  standalone: true,
  templateUrl: './kpi.component.html',
  styleUrl: './kpi.component.scss',
})
export class KpiComponent {
  readonly libelle = input.required<string>();
  readonly valeur = input.required<string>();
  readonly unite = input<string | null>(null);
  readonly detail = input<string | null>(null);
  readonly aide = input<string | null>(null);
  /** Valeurs numériques brutes pour l'écart (facultatives). */
  readonly actuel = input<number | null>(null);
  readonly precedent = input<number | null>(null);
  readonly sensFavorable = input<'hausse' | 'baisse'>('baisse');

  readonly ecart = computed(() => ecartRelatif(this.actuel(), this.precedent()));
  readonly ecartTexte = computed(() => (this.tendance() === 'stable' ? 'stable' : formatEcart(this.ecart())));
  readonly tendance = computed<'favorable' | 'defavorable' | 'stable' | null>(() => {
    const e = this.ecart();
    if (e === null) return null;
    if (Math.abs(e) < 0.005) return 'stable';
    const hausse = e > 0;
    return hausse === (this.sensFavorable() === 'hausse') ? 'favorable' : 'defavorable';
  });
  readonly icone = computed(() => {
    const e = this.ecart();
    if (e === null || Math.abs(e) < 0.005) return 'trending_flat';
    return e > 0 ? 'trending_up' : 'trending_down';
  });
}
