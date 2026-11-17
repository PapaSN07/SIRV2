import { Component, Input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'sir-notifications-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="sir-tabs" aria-label="Notifications">
      <a
        class="sir-tab"
        routerLink="/notifications/sms"
        routerLinkActive="sir-tab--active"
        [routerLinkActiveOptions]="{ exact: true }"
      >
        SMS envoyés
      </a>
      @if (showSend) {
        <a
          class="sir-tab"
          routerLink="/notifications/sms/envoyer"
          routerLinkActive="sir-tab--active"
        >
          Envoyer SMS
        </a>
      }
      @if (showDestinataires) {
        <a
          class="sir-tab"
          routerLink="/notifications/destinataires"
          routerLinkActive="sir-tab--active"
        >
          Destinataires
        </a>
      }
      @if (showEmails) {
        <a
          class="sir-tab"
          routerLink="/notifications/emails"
          routerLinkActive="sir-tab--active"
        >
          Emails
        </a>
      }
    </nav>
  `,
})
export class NotificationsNavComponent {
  @Input() showSend = true;
  @Input() showDestinataires = true;
  @Input() showEmails = true;
}
