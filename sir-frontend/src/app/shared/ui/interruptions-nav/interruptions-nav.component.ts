import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-interruptions-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="interruptions-nav" aria-label="Type d'interruption">
      <a
        class="interruptions-nav__tab"
        routerLink="/interruptions/distribution"
        routerLinkActive="interruptions-nav__tab--active"
        [routerLinkActiveOptions]="{ exact: false }"
      >
        Distribution
      </a>
      <a
        class="interruptions-nav__tab"
        routerLink="/interruptions/transport"
        routerLinkActive="interruptions-nav__tab--active"
        [routerLinkActiveOptions]="{ exact: false }"
      >
        Transport / OMVG
      </a>
    </nav>
  `,
  styles: [
    `
      .interruptions-nav {
        display: flex;
        gap: 0.25rem;
        margin-bottom: 1rem;
        padding: 0.25rem;
        background: #eef4fd;
        border-radius: 0.5rem;
        width: fit-content;
      }
      .interruptions-nav__tab {
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        font-size: 13px;
        font-weight: 600;
        color: #414750;
        text-decoration: none;
        transition: background 0.15s, color 0.15s;
      }
      .interruptions-nav__tab:hover {
        color: #3d49a0;
      }
      .interruptions-nav__tab--active {
        background: #fff;
        color: #3d49a0;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      }
    `,
  ],
})
export class InterruptionsNavComponent {}
