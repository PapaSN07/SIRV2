import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-analytics-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="analytics-nav" aria-label="Indicateurs et rapports">
      <a
        class="analytics-nav__tab"
        routerLink="/indicateurs"
        routerLinkActive="analytics-nav__tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        Indicateurs
      </a>
      <a
        class="analytics-nav__tab"
        routerLink="/rapports"
        routerLinkActive="analytics-nav__tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        Rapports CRSE
      </a>
    </nav>
  `,
  styles: [
    `
      .analytics-nav {
        display: flex;
        gap: 0.25rem;
        margin-bottom: 1rem;
        padding: 0.25rem;
        background: #eef4fd;
        border-radius: 0.5rem;
        width: fit-content;
      }
      .analytics-nav__tab {
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        font-size: 13px;
        font-weight: 600;
        color: #414750;
        text-decoration: none;
      }
      .analytics-nav__tab:hover {
        color: #3d49a0;
      }
      .analytics-nav__tab--active {
        background: #fff;
        color: #3d49a0;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      }
    `,
  ],
})
export class AnalyticsNavComponent {}
