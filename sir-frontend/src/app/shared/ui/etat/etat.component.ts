import { Component, input, output } from '@angular/core';

/**
 * État d'un bloc de données : chargement (squelette), vide ou erreur.
 * Messages en français, jamais de message technique ; « Réessayer » sur erreur.
 */
@Component({
  selector: 'sir-etat',
  standalone: true,
  template: `
    @switch (type()) {
      @case ('chargement') {
        <div class="etat etat--chargement" role="status" aria-live="polite">
          <span class="etat__squelette" [style.height]="hauteur()"></span>
          <span class="sr-only">Chargement en cours…</span>
        </div>
      }
      @case ('vide') {
        <div class="etat etat--vide" role="status">
          <span class="material-symbols-outlined" aria-hidden="true">inbox</span>
          <p>{{ message() || 'Aucune interruption sur la période et les filtres choisis.' }}</p>
          @if (actionVide()) {
            <button type="button" class="sir-btn sir-btn--sm sir-btn--outline" (click)="action.emit()">
              {{ actionVide() }}
            </button>
          }
        </div>
      }
      @case ('erreur') {
        <div class="etat etat--erreur" role="alert">
          <span class="material-symbols-outlined" aria-hidden="true">error</span>
          <p>{{ message() || 'Les données n’ont pas pu être chargées.' }}</p>
          <button type="button" class="sir-btn sir-btn--sm sir-btn--outline" (click)="reessayer.emit()">
            Réessayer
          </button>
        </div>
      }
    }
  `,
  styleUrl: './etat.component.scss',
})
export class EtatComponent {
  readonly type = input.required<'chargement' | 'vide' | 'erreur'>();
  readonly message = input<string | null>(null);
  /** Libellé d'une action proposée sur un état vide (ex. « Effacer les filtres »). */
  readonly actionVide = input<string | null>(null);
  readonly hauteur = input('160px');
  readonly reessayer = output<void>();
  readonly action = output<void>();
}
