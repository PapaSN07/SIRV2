import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { NotificationDestinataireService } from '../services/notification-destinataire.service';
import {
  Destinataire,
  DestinataireCreate,
  Exploitation,
  GroupeEnvoi,
} from '../../../shared/models/notification.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { NotificationsNavComponent } from '../../../shared/ui/notifications-nav/notifications-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

interface DestForm {
  nom: string;
  fonction: string;
  matricule: string;
  telephone: string;
  email: string;
  is_active: boolean;
  groupeIds: Set<number>;
}

interface GroupeForm {
  id: number | null;
  libelle: string;
  exploitation: Exploitation | '';
}

/**
 * Répertoire SMS (SIR v1 : Destinataire + GroupeEnvoi) : groupes d'envoi à gauche,
 * destinataires du groupe choisi à droite. Une personne peut appartenir à plusieurs groupes.
 */
@Component({
  selector: 'sir-destinataires-list',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, NotificationsNavComponent, PaginatorComponent],
  templateUrl: './destinataires-list.component.html',
  styleUrl: './destinataires-list.component.scss',
})
export class DestinatairesListComponent implements OnInit {
  private readonly service = inject(NotificationDestinataireService);
  private readonly auth = inject(AuthService);

  readonly exploitations: Exploitation[] = ['BCC', 'BRC', 'DISPATCHING'];
  readonly pageSize = 20;
  readonly items = signal<Destinataire[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly form = signal<DestForm>(this.emptyForm());

  readonly groupes = signal<GroupeEnvoi[]>([]);
  readonly groupeFiltre = signal<number | null>(null);
  readonly recherche = signal('');
  readonly afficherInactifs = signal(false);
  readonly groupeForm = signal<GroupeForm | null>(null);

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING', 'ADMIN_SAQS'));
  readonly groupesActifs = computed(() => this.groupes().filter((g) => g.is_active));
  readonly groupesVisibles = computed(() =>
    this.afficherInactifs() ? this.groupes() : this.groupesActifs(),
  );
  readonly groupeCourant = computed(() => this.groupes().find((g) => g.id === this.groupeFiltre()) ?? null);

  private rechercheTimer: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.loadGroupes();
    this.load();
  }

  // ── Groupes ────────────────────────────────────────────────────────────

  choisirGroupe(id: number | null): void {
    this.groupeFiltre.set(id);
    this.page.set(1);
    this.load();
  }

  nouveauGroupe(): void {
    this.groupeForm.set({ id: null, libelle: '', exploitation: '' });
    this.error.set(null);
  }

  modifierGroupe(g: GroupeEnvoi): void {
    this.groupeForm.set({ id: g.id, libelle: g.libelle, exploitation: g.exploitation ?? '' });
    this.error.set(null);
  }

  patchGroupeForm(key: 'libelle' | 'exploitation', value: string): void {
    this.groupeForm.update((f) => (f ? { ...f, [key]: value } : f));
  }

  annulerGroupe(): void {
    this.groupeForm.set(null);
  }

  enregistrerGroupe(): void {
    const f = this.groupeForm();
    if (!f) return;
    const libelle = f.libelle.trim();
    if (!libelle) {
      this.error.set('Le nom du groupe est obligatoire.');
      return;
    }
    const exploitation = f.exploitation || null;
    this.saving.set(true);
    const appel = f.id
      ? this.service.updateGroupe(f.id, { libelle, exploitation })
      : this.service.createGroupe({ libelle, exploitation });
    appel.subscribe({
      next: () => {
        this.saving.set(false);
        this.groupeForm.set(null);
        this.loadGroupes();
        this.load();
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.saving.set(false);
      },
    });
  }

  basculerActivationGroupe(g: GroupeEnvoi): void {
    if (g.is_active && !confirm(`Désactiver le groupe « ${g.libelle} » ? Ses membres sont conservés.`)) return;
    this.service.updateGroupe(g.id, { is_active: !g.is_active }).subscribe({
      next: () => this.loadGroupes(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  // ── Destinataires ─────────────────────────────────────────────────────

  onRecherche(valeur: string): void {
    this.recherche.set(valeur);
    if (this.rechercheTimer) clearTimeout(this.rechercheTimer);
    this.rechercheTimer = setTimeout(() => {
      this.page.set(1);
      this.load();
    }, 300);
  }

  onPageChange(next: number): void {
    this.page.set(next);
    this.load();
  }

  openCreate(): void {
    this.editingId.set(null);
    const f = this.emptyForm();
    const g = this.groupeFiltre();
    if (g) f.groupeIds.add(g);
    this.form.set(f);
    this.formOpen.set(true);
    this.error.set(null);
  }

  openEdit(item: Destinataire): void {
    this.editingId.set(item.id);
    this.form.set({
      nom: item.nom,
      fonction: item.fonction ?? '',
      matricule: item.matricule ? String(item.matricule) : '',
      telephone: item.telephone ?? '',
      email: item.email ?? '',
      is_active: item.is_active,
      groupeIds: new Set(item.groupes.map((g) => g.id)),
    });
    this.formOpen.set(true);
    this.error.set(null);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  patchForm(key: 'nom' | 'fonction' | 'matricule' | 'telephone' | 'email' | 'is_active', value: string | boolean): void {
    this.form.update((f) => ({ ...f, [key]: value }));
  }

  basculerGroupeForm(id: number): void {
    this.form.update((f) => {
      const groupeIds = new Set(f.groupeIds);
      if (groupeIds.has(id)) groupeIds.delete(id);
      else groupeIds.add(id);
      return { ...f, groupeIds };
    });
  }

  save(): void {
    const f = this.form();
    if (!f.nom.trim()) {
      this.error.set('Le nom est obligatoire.');
      return;
    }
    const matricule = f.matricule.trim() ? Number(f.matricule) : null;
    if (matricule !== null && (!Number.isInteger(matricule) || matricule < 0)) {
      this.error.set('Le matricule doit être un nombre entier.');
      return;
    }
    this.saving.set(true);
    this.error.set(null);

    const commun = {
      nom: f.nom.trim(),
      fonction: f.fonction.trim() || null,
      matricule,
      telephone: f.telephone.trim() || null,
      email: f.email.trim() || null,
      groupe_ids: [...f.groupeIds],
    };
    const id = this.editingId();
    const appel = id
      ? this.service.update(id, { ...commun, is_active: f.is_active })
      : this.service.create(commun as DestinataireCreate);
    appel.subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
        this.loadGroupes();
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.saving.set(false);
      },
    });
  }

  deactivate(item: Destinataire): void {
    if (!confirm(`Désactiver le destinataire « ${item.nom} » ?`)) return;
    this.service.delete(item.id).subscribe({
      next: () => {
        this.load();
        this.loadGroupes();
      },
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private loadGroupes(): void {
    this.service.listGroupesEnvoi(true).subscribe({
      next: (groupes) => this.groupes.set(groupes),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.service
      .listDestinataires(this.page(), this.pageSize, undefined, {
        groupeId: this.groupeFiltre(),
        recherche: this.recherche(),
      })
      .subscribe({
        next: (res) => {
          this.items.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
  }

  private emptyForm(): DestForm {
    return { nom: '', fonction: '', matricule: '', telephone: '', email: '', is_active: true, groupeIds: new Set() };
  }
}
