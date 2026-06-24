import { Component, Input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-notifications-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="notifications-nav" aria-label="Notifications">
      <a
        class="notifications-nav__tab"
        routerLink="/notifications/sms"
        routerLinkActive="notifications-nav__tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        SMS envoyés
      </a>
      @if (showSend) {
        <a
          class="notifications-nav__tab"
          routerLink="/notifications/sms/envoyer"
          routerLinkActive="notifications-nav__tab--active"
        >
          Envoyer SMS
        </a>
      }
      @if (showDestinataires) {
        <a
          class="notifications-nav__tab"
          routerLink="/notifications/destinataires"
          routerLinkActive="notifications-nav__tab--active"
        >
          Destinataires
        </a>
      }
      @if (showEmails) {
        <a
          class="notifications-nav__tab"
          routerLink="/notifications/emails"
          routerLinkActive="notifications-nav__tab--active"
        >
          Emails
        </a>
      }
    </nav>
  `,
  styles: [
    `
      .notifications-nav {
        display: flex;
        flex-wrap: wrap;
        gap: 0.25rem;
        margin-bottom: 1rem;
        padding: 0.25rem;
        background: #f3eef8;
        border-radius: 0.5rem;
      }
      .notifications-nav__tab {
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        font-size: 13px;
        font-weight: 600;
        color: #5c4d68;
        text-decoration: none;
      }
      .notifications-nav__tab--active {
        background: #fff;
        color: #3c1053;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
      }
    `,
  ],
})
export class NotificationsNavComponent {
  @Input() showSend = true;
  @Input() showDestinataires = true;
  @Input() showEmails = true;
}
