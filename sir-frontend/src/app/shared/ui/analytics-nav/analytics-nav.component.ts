import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-analytics-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="sir-tabs" aria-label="Indicateurs et rapports">
      <a
        class="sir-tab"
        routerLink="/indicateurs"
        routerLinkActive="sir-tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        Indicateurs
      </a>
      <a
        class="sir-tab"
        routerLink="/indicateurs/base-clients"
        routerLinkActive="sir-tab--active"
      >
        Base clients
      </a>
      <a
        class="sir-tab"
        routerLink="/rapports"
        routerLinkActive="sir-tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        Rapports Distribution
      </a>
    </nav>
  `,
})
export class AnalyticsNavComponent {}
