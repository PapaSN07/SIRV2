import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { map } from 'rxjs';

export interface OngletAVenir {
  titre: string;
  etape: number;
  contenu: string[];
}

/**
 * Onglet pas encore construit : dit ce qu'il contiendra et à quelle étape de la fusion
 * (docs/fusion_suivi_incidents.md §7). Remplacé onglet par onglet.
 */
@Component({
  selector: 'sir-onglet-a-venir',
  standalone: true,
  template: `
    @if (onglet(); as o) {
      <section class="sir-card a-venir" [attr.aria-labelledby]="'titre-' + o.etape">
        <span class="material-symbols-outlined a-venir__icone" aria-hidden="true">construction</span>
        <div>
          <h2 [id]="'titre-' + o.etape">{{ o.titre }}</h2>
          <p class="a-venir__etape">En construction — étape {{ o.etape }} de la fusion du suivi des incidents.</p>
          <p>Cet onglet contiendra :</p>
          <ul>
            @for (ligne of o.contenu; track ligne) {
              <li>{{ ligne }}</li>
            }
          </ul>
        </div>
      </section>
    }
  `,
  styleUrl: './onglet-a-venir.component.scss',
})
export class OngletAVenirComponent {
  readonly onglet = toSignal(inject(ActivatedRoute).data.pipe(map((d) => d['ongletAVenir'] as OngletAVenir)));
}
