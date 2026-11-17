import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin, of, switchMap } from 'rxjs';
import { GeoService } from '../../geo/services/geo.service';
import { Service } from '../../../shared/models/geo.models';
import { AuthService } from '../../../core/auth/auth.service';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { AdminUtilisateurService } from '../services/admin-utilisateur.service';
import {
  AnnuaireUtilisateur,
  RoleDetail,
  UtilisateurAdmin,
  UtilisateurCreate,
  UtilisateurUpdate,
} from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

const ROLES_AVEC_SERVICE = ['BCC', 'BRC', 'SUPERVISEUR'];

interface UserFormState {
  login: string;
  password: string;
  nom: string;
  prenom: string;
  email: string;
  matricule: string;
  telephone: string;
  selectedRoleIds: number[];
  /** Service de rattachement par rôle (BCC, BRC, Superviseur : obligatoire) */
  roleScopes: Record<number, number | null>;
  reset_password: string;
  /** Compte importé de l'Active Directory : connexion avec le mot de passe Windows */
  annuaire: boolean;
}

@Component({
  selector: 'sir-utilisateurs-list',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  templateUrl: './utilisateurs-list.component.html',
  styleUrl: './utilisateurs-list.component.scss',
})
export class UtilisateursListComponent implements OnInit {
  private readonly adminUsers = inject(AdminUtilisateurService);
  private readonly adminAdvanced = inject(AdminAdvancedService);
  private readonly auth = inject(AuthService);

  readonly roleOptions = signal<RoleDetail[]>([]);
  private readonly geo = inject(GeoService);
  /** Services de toutes les régions, pour le rattachement des rôles BCC / BRC / Superviseur */
  readonly services = signal<Service[]>([]);
  readonly pageSize = 20;

  readonly users = signal<UtilisateurAdmin[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  /** Texte recherché : login, matricule, nom, prénom ou e-mail. */
  readonly recherche = signal('');
  private delaiRecherche: ReturnType<typeof setTimeout> | null = null;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly form = signal<UserFormState>(this.emptyForm());

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING'));

  // Ajout depuis l'annuaire (LDAP / Active Directory)
  readonly annuaireOuvert = signal(false);
  readonly annuaireTexte = signal('');
  readonly annuaireResultats = signal<AnnuaireUtilisateur[]>([]);
  readonly annuaireChargement = signal(false);
  readonly annuaireErreur = signal<string | null>(null);
  private delaiAnnuaire: ReturnType<typeof setTimeout> | null = null;

  ngOnInit(): void {
    this.adminAdvanced.listRoles().subscribe({
      next: (roles) => this.roleOptions.set(roles.filter((r) => r.is_active && r.nom !== 'SUPERADMIN')),
      error: () => {},
    });
    this.geo
      .getRegions()
      .pipe(
        switchMap((regions) => (regions.length ? forkJoin(regions.map((r) => this.geo.getServicesByRegion(r.id))) : of([]))),
      )
      .subscribe({
        next: (listes) => {
          const parId = new Map(listes.flat().map((sv) => [sv.id, sv]));
          this.services.set([...parId.values()].sort((a, b) => a.libelle.localeCompare(b.libelle)));
        },
        error: () => {},
      });
    this.load();
  }

  onPageChange(nextPage: number): void {
    this.page.set(nextPage);
    this.load();
  }

  ouvrirAnnuaire(): void {
    this.closeForm();
    this.annuaireOuvert.set(true);
    this.annuaireErreur.set(null);
  }

  fermerAnnuaire(): void {
    this.annuaireOuvert.set(false);
    this.annuaireTexte.set('');
    this.annuaireResultats.set([]);
  }

  /** Recherche dans l'annuaire 400 ms après la dernière touche (2 caractères au moins). */
  onAnnuaire(texte: string): void {
    this.annuaireTexte.set(texte);
    if (this.delaiAnnuaire) clearTimeout(this.delaiAnnuaire);
    if (texte.trim().length < 2) {
      this.annuaireResultats.set([]);
      return;
    }
    this.delaiAnnuaire = setTimeout(() => {
      this.annuaireChargement.set(true);
      this.annuaireErreur.set(null);
      this.adminAdvanced.rechercherAnnuaire(texte.trim()).subscribe({
        next: (res) => {
          this.annuaireResultats.set(res);
          this.annuaireChargement.set(false);
        },
        error: (err: Error) => {
          this.annuaireErreur.set(err.message);
          this.annuaireChargement.set(false);
        },
      });
    }, 400);
  }

  /** Prépare la fiche avec les informations de l'annuaire ; il reste à choisir les rôles. */
  ajouterDepuisAnnuaire(compte: AnnuaireUtilisateur): void {
    const morceaux = (compte.nom_affiche ?? '').trim().split(/\s+/);
    this.editingId.set(null);
    this.form.set({
      ...this.emptyForm(),
      login: compte.login,
      nom: compte.nom ?? morceaux.slice(1).join(' '),
      prenom: compte.prenom ?? morceaux[0] ?? '',
      email: compte.email ?? '',
      telephone: compte.telephone ?? '',
      matricule: compte.matricule ?? '',
      annuaire: true,
    });
    this.fermerAnnuaire();
    this.formOpen.set(true);
    this.error.set(null);
  }

  openCreate(): void {
    this.annuaireOuvert.set(false);
    this.editingId.set(null);
    this.form.set(this.emptyForm());
    this.formOpen.set(true);
    this.error.set(null);
  }

  openEdit(user: UtilisateurAdmin): void {
    this.editingId.set(user.id);
    this.form.set({
      login: user.login,
      password: '',
      nom: user.nom,
      prenom: user.prenom,
      email: user.email ?? '',
      telephone: user.telephone ?? '',
      matricule: user.matricule ?? '',
      selectedRoleIds: user.roles.map((r) => r.role_id),
      roleScopes: Object.fromEntries(user.roles.map((r) => [r.role_id, r.scope_service_id])),
      reset_password: '',
      annuaire: false,
    });
    this.formOpen.set(true);
    this.error.set(null);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
    this.form.set(this.emptyForm());
  }

  patchForm(field: keyof UserFormState, value: string | number[] | boolean): void {
    this.form.update((current) => ({ ...current, [field]: value }));
  }

  /** Rôles opérationnels rattachés à un service (périmètre de saisie, de lecture ou de validation). */
  roleAvecService(nom: string): boolean {
    return ROLES_AVEC_SERVICE.includes(nom);
  }

  /** Liste « Service » affichée pour un rôle coché : rôle opérationnel ou rôle créé dans la matrice. */
  afficherService(role: RoleDetail): boolean {
    return this.isRoleSelected(role.id) && (this.roleAvecService(role.nom) || !role.systeme);
  }

  serviceDuRole(roleId: number): number | null {
    return this.form().roleScopes[roleId] ?? null;
  }

  choisirService(roleId: number, valeur: string): void {
    this.form.update((f) => ({ ...f, roleScopes: { ...f.roleScopes, [roleId]: valeur ? Number(valeur) : null } }));
  }

  isRoleSelected(roleId: number): boolean {
    return this.form().selectedRoleIds.includes(roleId);
  }

  toggleRole(roleId: number): void {
    this.form.update((current) => {
      const ids = [...current.selectedRoleIds];
      const idx = ids.indexOf(roleId);
      if (idx >= 0) ids.splice(idx, 1);
      else ids.push(roleId);
      return { ...current, selectedRoleIds: ids };
    });
  }

  saveForm(): void {
    const state = this.form();
    if (!state.nom.trim() || !state.prenom.trim()) {
      this.error.set('Nom et prénom sont obligatoires.');
      return;
    }
    if (state.selectedRoleIds.length === 0) {
      this.error.set('Au moins un rôle est obligatoire.');
      return;
    }
    const sansService = this.roleOptions().find(
      (r) => state.selectedRoleIds.includes(r.id) && this.roleAvecService(r.nom) && !state.roleScopes[r.id],
    );
    if (sansService) {
      this.error.set(`Choisissez le service de rattachement du rôle ${sansService.nom}.`);
      return;
    }

    this.saving.set(true);
    this.error.set(null);
    const editId = this.editingId();
    const roles = state.selectedRoleIds.map((role_id) => {
      const role = this.roleOptions().find((r) => r.id === role_id);
      const avecService = role !== undefined && (this.roleAvecService(role.nom) || !role.systeme);
      return { role_id, scope_service_id: avecService ? (state.roleScopes[role_id] ?? null) : null };
    });

    if (editId === null) {
      if (!state.login.trim() || (!state.annuaire && state.password.length < 8)) {
        this.error.set('Login et mot de passe (8 car. min.) sont obligatoires.');
        this.saving.set(false);
        return;
      }
      const body: UtilisateurCreate = {
        login: state.login.trim(),
        password: state.annuaire ? null : state.password,
        annuaire: state.annuaire,
        nom: state.nom.trim(),
        prenom: state.prenom.trim(),
        email: state.email.trim() || null,
        telephone: state.telephone.trim() || null,
        matricule: state.matricule.trim() || null,
        roles,
      };
      this.adminUsers.create(body).subscribe({
        next: () => this.afterSave(),
        error: (err: Error) => this.onSaveError(err),
      });
      return;
    }

    const body: UtilisateurUpdate = {
      nom: state.nom.trim(),
      prenom: state.prenom.trim(),
      email: state.email.trim() || null,
      telephone: state.telephone.trim() || null,
      matricule: state.matricule.trim() || null,
      roles,
    };
    this.adminUsers.update(editId, body).subscribe({
      next: () => {
        if (state.reset_password.length >= 8) {
          this.adminUsers.resetPassword(editId, { new_password: state.reset_password }).subscribe({
            next: () => this.afterSave(),
            error: (err: Error) => this.onSaveError(err),
          });
        } else {
          this.afterSave();
        }
      },
      error: (err: Error) => this.onSaveError(err),
    });
  }

  toggleActive(user: UtilisateurAdmin): void {
    const action = user.is_active ? this.adminUsers.desactiver(user.id) : this.adminUsers.activer(user.id);
    action.subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  rolesLabel(user: UtilisateurAdmin): string {
    return user.roles.map((r) => r.role_nom).join(', ') || '—';
  }

  private afterSave(): void {
    this.saving.set(false);
    this.closeForm();
    this.load();
  }

  private onSaveError(err: Error): void {
    this.error.set(err.message);
    this.saving.set(false);
  }

  /** Recherche à la frappe, lancée 300 ms après la dernière touche, depuis la première page. */
  onRecherche(texte: string): void {
    this.recherche.set(texte);
    if (this.delaiRecherche) clearTimeout(this.delaiRecherche);
    this.delaiRecherche = setTimeout(() => {
      this.page.set(1);
      this.load();
    }, 300);
  }

  effacerRecherche(): void {
    this.onRecherche('');
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminUsers.list(this.page(), this.pageSize, this.recherche()).subscribe({
      next: (res) => {
        this.users.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }

  private emptyForm(): UserFormState {
    return {
      login: '',
      password: '',
      nom: '',
      prenom: '',
      email: '',
      telephone: '',
      matricule: '',
      selectedRoleIds: [],
      roleScopes: {},
      reset_password: '',
      annuaire: false,
    };
  }
}
