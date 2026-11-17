import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { FONCTIONNALITES } from '../../../core/config/fonctionnalites';

@Component({
  selector: 'sir-interruptions-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    @if (transport) {
    <nav class="sir-tabs" aria-label="Type d'interruption">
      <a
        class="sir-tab"
        routerLink="/interruptions/distribution"
        routerLinkActive="sir-tab--active"
        [routerLinkActiveOptions]="{ exact: false }"
      >
        Distribution
      </a>
      <a
        class="sir-tab"
        routerLink="/interruptions/transport"
        routerLinkActive="sir-tab--active"
        [routerLinkActiveOptions]="{ exact: false }"
      >
        Transport / OMVG
      </a>
    </nav>
    }
  `,
})
export class InterruptionsNavComponent {
  /** Un seul onglet (Distribution) quand le transport est masqué : pas de barre. */
  readonly transport = FONCTIONNALITES.transport;
}
