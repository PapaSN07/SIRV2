import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { ReseauAdminDistributionService } from '../services/reseau-admin-distribution.service';
import {
  Feeder,
  FeederCreate,
  FeederUpdate,
  Poste,
  PosteCreate,
  PosteSource,
  PosteUpdate,
} from '../../../shared/models/reseau.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

type ReseauDistTab = 'feeders' | 'postes';

@Component({
  selector: 'sir-reseau-distribution-admin',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  templateUrl: './reseau-distribution-admin.component.html',
  styleUrl: './reseau-distribution-admin.component.scss',
})
export class ReseauDistributionAdminComponent implements OnInit {
  private readonly reseau = inject(ReseauAdminDistributionService);
  private readonly auth = inject(AuthService);

  readonly pageSize = 20;
  readonly activeTab = signal<ReseauDistTab>('feeders');
  readonly feeders = signal<Feeder[]>([]);
  readonly feedersOptions = signal<Feeder[]>([]);
  readonly postes = signal<Poste[]>([]);
  readonly postesSources = signal<PosteSource[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);

  readonly feederForm = signal({ code: '', libelle: '', poste_source_id: '', is_active: true });
  readonly posteForm = signal({ code: '', libelle: '', feeder_id: '', is_active: true });

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR'));

  ngOnInit(): void {
    this.loadPostesSources();
    this.loadFeedersForSelect();
    this.load();
  }

  onTabChange(tab: ReseauDistTab): void {
    this.activeTab.set(tab);
    this.page.set(1);
    this.closeForm();
    this.load();
  }

  onPageChange(nextPage: number): void {
    this.page.set(nextPage);
    this.load();
  }

  openCreate(): void {
    this.editingId.set(null);
    if (this.activeTab() === 'feeders') {
      this.feederForm.set({ code: '', libelle: '', poste_source_id: '', is_active: true });
    } else {
      this.posteForm.set({ code: '', libelle: '', feeder_id: '', is_active: true });
    }
    this.formOpen.set(true);
    this.error.set(null);
  }

  openEditFeeder(item: Feeder): void {
    this.editingId.set(item.id);
    this.feederForm.set({
      code: item.code,
      libelle: item.libelle,
      poste_source_id: String(item.poste_source_id),
      is_active: item.is_active,
    });
    this.formOpen.set(true);
  }

  openEditPoste(item: Poste): void {
    this.editingId.set(item.id);
    this.posteForm.set({
      code: item.code,
      libelle: item.libelle,
      feeder_id: item.feeder_id ? String(item.feeder_id) : '',
      is_active: item.is_active,
    });
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  patchFeederForm(field: 'code' | 'libelle' | 'poste_source_id' | 'is_active', value: string | boolean): void {
    this.feederForm.update((current) => ({ ...current, [field]: value }));
  }

  patchPosteForm(field: 'code' | 'libelle' | 'feeder_id' | 'is_active', value: string | boolean): void {
    this.posteForm.update((current) => ({ ...current, [field]: value }));
  }

  saveForm(): void {
    if (this.activeTab() === 'feeders') {
      this.saveFeeder();
    } else {
      this.savePoste();
    }
  }

  deactivateFeeder(item: Feeder): void {
    if (!confirm(`Désactiver le feeder « ${item.libelle} » ?`)) return;
    this.reseau.deleteFeeder(item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  deactivatePoste(item: Poste): void {
    if (!confirm(`Désactiver le poste « ${item.libelle} » ?`)) return;
    this.reseau.deletePoste(item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private saveFeeder(): void {
    const f = this.feederForm();
    const posteSourceId = Number(f.poste_source_id);
    if (!f.code.trim() || !f.libelle.trim() || !posteSourceId) {
      this.error.set('Code, libellé et poste source sont obligatoires.');
      return;
    }
    this.saving.set(true);
    const editId = this.editingId();
    if (editId === null) {
      const body: FeederCreate = {
        code: f.code.trim(),
        libelle: f.libelle.trim(),
        poste_source_id: posteSourceId,
      };
      this.reseau.createFeeder(body).subscribe({
        next: () => this.afterSave(),
        error: (err: Error) => this.onSaveError(err),
      });
      return;
    }
    const body: FeederUpdate = {
      code: f.code.trim(),
      libelle: f.libelle.trim(),
      poste_source_id: posteSourceId,
      is_active: f.is_active,
    };
    this.reseau.updateFeeder(editId, body).subscribe({
      next: () => this.afterSave(),
      error: (err: Error) => this.onSaveError(err),
    });
  }

  private savePoste(): void {
    const f = this.posteForm();
    if (!f.code.trim() || !f.libelle.trim()) {
      this.error.set('Code et libellé sont obligatoires.');
      return;
    }
    this.saving.set(true);
    const feederId = f.feeder_id ? Number(f.feeder_id) : null;
    const editId = this.editingId();
    if (editId === null) {
      const body: PosteCreate = {
        code: f.code.trim(),
        libelle: f.libelle.trim(),
        feeder_id: feederId,
      };
      this.reseau.createPoste(body).subscribe({
        next: () => this.afterSave(),
        error: (err: Error) => this.onSaveError(err),
      });
      return;
    }
    const body: PosteUpdate = {
      code: f.code.trim(),
      libelle: f.libelle.trim(),
      feeder_id: feederId,
      is_active: f.is_active,
    };
    this.reseau.updatePoste(editId, body).subscribe({
      next: () => this.afterSave(),
      error: (err: Error) => this.onSaveError(err),
    });
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

  private loadPostesSources(): void {
    this.reseau.listPostesSources({ page: 1, page_size: 100 }).subscribe({
      next: (res) => this.postesSources.set(res.items),
    });
  }

  private loadFeedersForSelect(): void {
    this.reseau.listFeeders({ page: 1, page_size: 200 }).subscribe({
      next: (res) => this.feedersOptions.set(res.items),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const params = { page: this.page(), page_size: this.pageSize };

    if (this.activeTab() === 'feeders') {
      this.reseau.listFeeders(params).subscribe({
        next: (res) => {
          this.feeders.set(res.items);
          this.total.set(res.total);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
      return;
    }

    this.reseau.listPostes(params).subscribe({
      next: (res) => {
        this.postes.set(res.items);
        this.total.set(res.total);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }
}
