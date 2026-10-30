import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { AdminUtilisateurService } from '../../admin/services/admin-utilisateur.service';
import { NotificationDestinataireService } from '../services/notification-destinataire.service';
import { NotificationSmsService } from '../services/notification-sms.service';
import { Destinataire, GroupeEnvoi } from '../../../shared/models/notification.models';
import { UtilisateurAdmin } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { NotificationsNavComponent } from '../../../shared/ui/notifications-nav/notifications-nav.component';
import { toutesLesPages } from '../../../shared/utils/pagination.utils';

type TargetTab = 'destinataires' | 'utilisateurs';

@Component({
  selector: 'sir-sms-send',
  standalone: true,
  imports: [FormsModule, RouterLink, PageHeaderComponent, NotificationsNavComponent],
  templateUrl: './sms-send.component.html',
  styleUrl: './sms-send.component.scss',
})
export class SmsSendComponent implements OnInit {
  private readonly sms = inject(NotificationSmsService);
  private readonly destService = inject(NotificationDestinataireService);
  private readonly adminUsers = inject(AdminUtilisateurService);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly maxLength = 160;
  readonly message = signal('');
  readonly tab = signal<TargetTab>('destinataires');
  readonly destinataires = signal<Destinataire[]>([]);
  readonly utilisateurs = signal<UtilisateurAdmin[]>([]);
  readonly groupes = signal<GroupeEnvoi[]>([]);
  /** Groupe affiché (null = tous) et recherche libre (nom, fonction, numéro). */
  readonly groupeAffiche = signal<number | null>(null);
  readonly recherche = signal('');
  readonly selectedDestIds = signal<Set<number>>(new Set());
  readonly selectedUserIds = signal<Set<number>>(new Set());
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly success = signal<string | null>(null);

  readonly charCount = computed(() => this.message().length);

  readonly destinatairesAffiches = computed(() => {
    const groupe = this.groupeAffiche();
    const q = this.recherche().trim().toLowerCase();
    return this.destinataires().filter(
      (d) =>
        (groupe === null || d.groupe_id === groupe) &&
        (!q || [d.nom, d.fonction, d.telephone, d.groupe_libelle].some((v) => (v ?? '').toLowerCase().includes(q))),
    );
  });

  readonly tousAffichesCoches = computed(() => {
    const liste = this.destinatairesAffiches();
    const sel = this.selectedDestIds();
    return liste.length > 0 && liste.every((d) => sel.has(d.id));
  });
  readonly canSend = computed(
    () =>
      this.message().trim().length > 0 &&
      (this.selectedDestIds().size > 0 || this.selectedUserIds().size > 0),
  );

  ngOnInit(): void {
    if (!this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS')) {
      void this.router.navigate(['/notifications/sms']);
      return;
    }
    this.loadTargets();
  }

  setTab(tab: TargetTab): void {
    this.tab.set(tab);
  }

  onMessageInput(value: string): void {
    this.message.set(value.slice(0, this.maxLength));
  }

  afficherGroupe(id: number | null): void {
    this.groupeAffiche.set(id);
  }

  /** Coche (ou décoche si tout est déjà coché) les destinataires affichés : un groupe entier en un clic. */
  basculerAffiches(): void {
    const next = new Set(this.selectedDestIds());
    const liste = this.destinatairesAffiches();
    if (this.tousAffichesCoches()) liste.forEach((d) => next.delete(d.id));
    else liste.forEach((d) => next.add(d.id));
    this.selectedDestIds.set(next);
  }

  toggleDest(id: number): void {
    const next = new Set(this.selectedDestIds());
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.selectedDestIds.set(next);
  }

  toggleUser(user: UtilisateurAdmin): void {
    if (!user.telephone) return;
    const next = new Set(this.selectedUserIds());
    if (next.has(user.id)) next.delete(user.id);
    else next.add(user.id);
    this.selectedUserIds.set(next);
  }

  isDestSelected(id: number): boolean {
    return this.selectedDestIds().has(id);
  }

  isUserSelected(id: number): boolean {
    return this.selectedUserIds().has(id);
  }

  submit(): void {
    if (!this.canSend() || this.saving()) return;
    this.saving.set(true);
    this.error.set(null);
    this.success.set(null);

    const destIds = [...this.selectedDestIds()];
    const userIds = [...this.selectedUserIds()];

    this.sms
      .send({
        message: this.message().trim(),
        destinataire_ids: destIds.length ? destIds : undefined,
        utilisateur_ids: userIds.length ? userIds : undefined,
      })
      .subscribe({
        next: (res) => {
          this.saving.set(false);
          this.success.set(`${res.sent_count} SMS mis en file d'envoi.`);
          void this.router.navigate(['/notifications/sms']);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
  }

  private loadTargets(): void {
    this.loading.set(true);
    // L'API limite page_size à 100 : on charge toutes les pages
    toutesLesPages((page, size) => this.destService.listDestinataires(page, size, true)).subscribe({
      next: (items) => {
        this.destinataires.set(items.filter((d) => d.telephone));
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });

    this.destService.listGroupesEnvoi().subscribe({
      next: (groupes) => this.groupes.set(groupes.filter((g) => g.nb_destinataires > 0)),
      error: () => {},
    });

    toutesLesPages((page, size) => this.adminUsers.list(page, size)).subscribe({
      next: (items) => this.utilisateurs.set(items),
      error: () => {},
    });
  }
}
