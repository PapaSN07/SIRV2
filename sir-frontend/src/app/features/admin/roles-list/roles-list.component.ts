import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { FONCTIONNALITES } from '../../../core/config/fonctionnalites';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { PermissionInfo, RoleDetail } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';

/** Libellés des modules (ressources des permissions) dans l'ordre d'affichage. */
const MODULES: { ressource: string; libelle: string; icone: string }[] = [
  { ressource: 'interruptions_distribution', libelle: 'Interruptions distribution', icone: 'bolt' },
  { ressource: 'interruptions_transport', libelle: 'Interruptions transport', icone: 'electric_bolt' },
  { ressource: 'indicateurs', libelle: 'Indicateurs', icone: 'monitoring' },
  { ressource: 'rapports', libelle: 'Rapports', icone: 'assessment' },
  { ressource: 'assistant', libelle: 'Assistant', icone: 'psychology' },
  { ressource: 'notifications', libelle: 'Notifications (SMS, e-mails)', icone: 'notifications' },
  { ressource: 'napt', libelle: 'NAPT', icone: 'description' },
  { ressource: 'reseau', libelle: 'Réseau', icone: 'lan' },
  { ressource: 'admin_utilisateurs', libelle: 'Utilisateurs', icone: 'group' },
  { ressource: 'admin_roles', libelle: 'Rôles et droits', icone: 'admin_panel_settings' },
];

const ACTIONS: Record<string, string> = {
  read: 'Consulter',
  create: 'Créer',
  update: 'Modifier',
  validate: 'Valider',
  admin: 'Administrer',
};
const ORDRE_ACTIONS = ['read', 'create', 'update', 'validate', 'admin'];

interface LigneModule {
  ressource: string;
  libelle: string;
  icone: string;
  permissions: PermissionInfo[];
}

@Component({
  selector: 'sir-roles-list',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent],
  templateUrl: './roles-list.component.html',
  styleUrl: './roles-list.component.scss',
})
export class RolesListComponent implements OnInit {
  private readonly admin = inject(AdminAdvancedService);
  private readonly auth = inject(AuthService);

  readonly roles = signal<RoleDetail[]>([]);
  readonly permissions = signal<PermissionInfo[]>([]);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly afficherInactifs = signal(false);
  /** Droits modifiés, par rôle : ensemble complet des permissions cochées. */
  readonly brouillon = signal<Map<number, Set<number>>>(new Map());

  readonly formOuvert = signal(false);
  readonly nouveauNom = signal('');
  readonly nouvelleDescription = signal('');
  readonly modeleId = signal<number | null>(null);

  readonly peutModifier = computed(() => {
    this.auth.currentUser();
    return this.auth.hasPermission('admin_roles:update');
  });

  readonly colonnes = computed(() =>
    this.roles().filter((r) => r.nom !== 'SUPERADMIN' && (r.is_active || this.afficherInactifs())),
  );

  readonly lignes = computed<LigneModule[]>(() => {
    const perms = this.permissions().filter(
      (p) => FONCTIONNALITES.transport || p.ressource !== 'interruptions_transport',
    );
    const connus = new Set(MODULES.map((m) => m.ressource));
    const modules = [
      ...MODULES,
      ...[...new Set(perms.map((p) => p.ressource))]
        .filter((r) => !connus.has(r))
        .map((r) => ({ ressource: r, libelle: r, icone: 'extension' })),
    ];
    return modules
      .map((m) => ({
        ...m,
        permissions: perms
          .filter((p) => p.ressource === m.ressource)
          .sort((a, b) => ORDRE_ACTIONS.indexOf(a.action) - ORDRE_ACTIONS.indexOf(b.action)),
      }))
      .filter((m) => m.permissions.length > 0);
  });

  readonly nbModifies = computed(() => this.brouillon().size);

  ngOnInit(): void {
    this.charger();
  }

  libelleAction(action: string): string {
    return ACTIONS[action] ?? action;
  }

  /** Le compte ne modifie ni SUPERADMIN ni un rôle qu'il détient (pas d'auto-attribution de droits). */
  verrouille(role: RoleDetail): boolean {
    if (!this.peutModifier()) return true;
    if (this.auth.isExactRole('SUPERADMIN')) return false;
    return this.auth.isExactRole(role.nom);
  }

  coche(role: RoleDetail, permissionId: number): boolean {
    const modif = this.brouillon().get(role.id);
    if (modif) return modif.has(permissionId);
    return role.permissions.some((p) => p.id === permissionId);
  }

  modifie(role: RoleDetail): boolean {
    return this.brouillon().has(role.id);
  }

  basculer(role: RoleDetail, permissionId: number): void {
    if (this.verrouille(role)) return;
    this.message.set(null);
    const courant = new Set(this.brouillon().get(role.id) ?? role.permissions.map((p) => p.id));
    if (courant.has(permissionId)) courant.delete(permissionId);
    else courant.add(permissionId);
    const origine = new Set(role.permissions.map((p) => p.id));
    const identique = courant.size === origine.size && [...courant].every((id) => origine.has(id));
    this.brouillon.update((m) => {
      const suivant = new Map(m);
      if (identique) suivant.delete(role.id);
      else suivant.set(role.id, courant);
      return suivant;
    });
  }

  annuler(): void {
    this.brouillon.set(new Map());
    this.message.set(null);
  }

  enregistrer(): void {
    const modifs = [...this.brouillon().entries()];
    if (modifs.length === 0) return;
    this.saving.set(true);
    this.error.set(null);
    forkJoin(modifs.map(([id, perms]) => this.admin.updateRole(id, { permission_ids: [...perms] }))).subscribe({
      next: (maj) => {
        const parId = new Map(maj.map((r) => [r.id, r]));
        this.roles.update((roles) => roles.map((r) => parId.get(r.id) ?? r));
        this.brouillon.set(new Map());
        this.saving.set(false);
        this.message.set(
          `Droits enregistrés (${maj.length} rôle${maj.length > 1 ? 's' : ''}). Ils s'appliquent à la prochaine connexion des utilisateurs.`,
        );
      },
      error: (err: Error) => {
        this.saving.set(false);
        this.error.set(err.message);
      },
    });
  }

  ouvrirCreation(): void {
    this.nouveauNom.set('');
    this.nouvelleDescription.set('');
    this.modeleId.set(null);
    this.formOuvert.set(true);
    this.error.set(null);
  }

  creer(): void {
    const nom = this.nouveauNom().trim().toUpperCase().replace(/\s+/g, '_');
    if (!/^[A-Z][A-Z0-9_]{1,49}$/.test(nom)) {
      this.error.set('Nom du rôle : lettres, chiffres et « _ », en commençant par une lettre (ex. CHEF_UNITE).');
      return;
    }
    const modele = this.roles().find((r) => r.id === this.modeleId());
    const permissionIds = (modele?.permissions ?? [])
      .filter((p) => p.ressource !== 'admin_roles')
      .map((p) => p.id);
    this.saving.set(true);
    this.error.set(null);
    this.admin
      .createRole({ nom, description: this.nouvelleDescription().trim() || null, permission_ids: permissionIds })
      .subscribe({
        next: (role) => {
          this.roles.update((roles) => [...roles, role].sort((a, b) => a.nom.localeCompare(b.nom)));
          this.saving.set(false);
          this.formOuvert.set(false);
          this.message.set(`Rôle ${role.nom} créé : cochez ses droits dans la matrice puis enregistrez.`);
        },
        error: (err: Error) => {
          this.saving.set(false);
          this.error.set(err.message);
        },
      });
  }

  basculerActif(role: RoleDetail): void {
    const verbe = role.is_active ? 'Désactiver' : 'Réactiver';
    if (!confirm(`${verbe} le rôle ${role.nom} ?`)) return;
    this.admin.updateRole(role.id, { is_active: !role.is_active }).subscribe({
      next: (maj) => this.roles.update((roles) => roles.map((r) => (r.id === maj.id ? maj : r))),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private charger(): void {
    this.loading.set(true);
    forkJoin({ roles: this.admin.listRoles(), permissions: this.admin.listPermissions() }).subscribe({
      next: ({ roles, permissions }) => {
        this.roles.set(roles);
        this.permissions.set(permissions);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }
}
