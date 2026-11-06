import { Component, computed, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';

export interface BarreItem {
  libelle: string;
  valeur: number;
  /** Valeur de comparaison (semaine précédente…), barre fine sous la principale. */
  comparaison?: number | null;
  /** Texte ajouté après la valeur (part en %, nombre…). */
  detail?: string;
}

/** Barres horizontales légères (sans bibliothèque) : une ligne par élément, échelle commune. */
@Component({
  selector: 'sir-barres',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    @if (items().length === 0) {
      <p class="barres__vide">Aucune donnée sur la période.</p>
    } @else {
      @if (legende(); as l) {
        <p class="barres__legende">
          <span class="barres__puce"></span>{{ l[0] }}
          @if (aComparaison()) {
            <span class="barres__puce barres__puce--comparaison"></span>{{ l[1] }}
          }
        </p>
      }
      <ul class="barres" role="list">
        @for (item of items(); track item.libelle) {
          <li class="barres__ligne">
            <span class="barres__libelle" [title]="item.libelle">{{ item.libelle }}</span>
            <span class="barres__piste">
              <span class="barres__barre" [style.width.%]="largeur(item.valeur)"></span>
              @if (item.comparaison !== undefined && item.comparaison !== null) {
                <span class="barres__barre barres__barre--comparaison" [style.width.%]="largeur(item.comparaison)"></span>
              }
            </span>
            <span class="barres__valeur">
              {{ item.valeur | number: format() : 'fr-FR' }}{{ unite() }}
              @if (item.detail) {
                <small>{{ item.detail }}</small>
              }
            </span>
          </li>
        }
      </ul>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .barres {
        list-style: none;
        margin: 0;
        padding: 0;
        display: grid;
        gap: 0.5rem;
      }
      .barres__ligne {
        display: grid;
        grid-template-columns: minmax(7rem, 15rem) 1fr auto;
        align-items: center;
        gap: 0.75rem;
        font-size: 12px;
      }
      .barres__libelle {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: #1a0a2e;
      }
      .barres__piste {
        display: grid;
        gap: 2px;
      }
      .barres__barre {
        display: block;
        height: 12px;
        min-width: 2px;
        border-radius: 2px;
        background: #3c1053;
        transition: width 0.3s ease;
      }
      .barres__barre--comparaison {
        height: 5px;
        background: #f39200;
        opacity: 0.8;
      }
      .barres__valeur {
        min-width: 4.5rem;
        text-align: right;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
        color: #3c1053;
      }
      .barres__valeur small {
        display: block;
        font-weight: 400;
        color: #5c4d68;
      }
      .barres__legende {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        margin: 0 0 0.625rem;
        font-size: 11px;
        color: #5c4d68;
      }
      .barres__puce {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 2px;
        background: #3c1053;
      }
      .barres__puce--comparaison {
        margin-left: 0.75rem;
        background: #f39200;
      }
      .barres__vide {
        margin: 0;
        font-size: 13px;
        color: #5c4d68;
      }
      @media (max-width: 480px) {
        .barres__ligne {
          grid-template-columns: 1fr auto;
        }
        .barres__piste {
          grid-column: 1 / -1;
          grid-row: 2;
        }
      }
    `,
  ],
})
export class BarresComponent {
  readonly items = input.required<BarreItem[]>();
  readonly unite = input('');
  readonly format = input('1.0-2');
  /** [libellé de la barre principale, libellé de la comparaison] */
  readonly legende = input<[string, string] | null>(null);

  readonly aComparaison = computed(() => this.items().some((i) => i.comparaison !== undefined && i.comparaison !== null));
  private readonly max = computed(() =>
    Math.max(0, ...this.items().flatMap((i) => [i.valeur, i.comparaison ?? 0])),
  );

  largeur(valeur: number): number {
    const max = this.max();
    return max > 0 ? Math.max(0, (valeur / max) * 100) : 0;
  }
}
