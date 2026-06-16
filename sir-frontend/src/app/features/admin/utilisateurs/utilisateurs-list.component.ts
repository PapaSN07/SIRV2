import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { AdminUtilisateurService } from '../services/admin-utilisateur.service';
import {
  RoleDetail,
  UtilisateurAdmin,
  UtilisateurCreate,
  UtilisateurUpdate,
} from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

interface UserFormState {
  login: string;
  password: string;
  nom: string;
  prenom: string;
  email: string;
  telephone: string;
  selectedRoleIds: number[];
  reset_password: string;
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
  readonly pageSize = 20;

  readonly users = signal<UtilisateurAdmin[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly form = signal<UserFormState>(this.emptyForm());

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING'));

  ngOnInit(): void {
    this.adminAdvanced.listRoles().subscribe({
      next: (roles) => this.roleOptions.set(roles),
      error: () => {},
    });
    this.load();
  }

  onPageChange(nextPage: number): void {
    this.page.set(nextPage);
    this.load();
  }

  openCreate(): void {
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
      selectedRoleIds: user.roles.map((r) => r.role_id),
      reset_password: '',
    });
    this.formOpen.set(true);
    this.error.set(null);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
    this.form.set(this.emptyForm());
  }

  patchForm(field: keyof UserFormState, value: string | number[]): void {
    this.form.update((current) => ({ ...current, [field]: value }));
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

    this.saving.set(true);
    this.error.set(null);
    const editId = this.editingId();
    const roles = state.selectedRoleIds.map((role_id) => ({ role_id }));

    if (editId === null) {
      if (!state.login.trim() || state.password.length < 8) {
        this.error.set('Login et mot de passe (8 car. min.) sont obligatoires.');
        this.saving.set(false);
        return;
      }
      const body: UtilisateurCreate = {
        login: state.login.trim(),
        password: state.password,
        nom: state.nom.trim(),
        prenom: state.prenom.trim(),
        email: state.email.trim() || null,
        telephone: state.telephone.trim() || null,
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

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.adminUsers.list(this.page(), this.pageSize).subscribe({
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
      selectedRoleIds: [],
      reset_password: '',
    };
  }
}
