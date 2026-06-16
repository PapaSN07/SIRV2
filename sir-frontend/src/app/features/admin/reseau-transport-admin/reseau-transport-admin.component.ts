import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { ReseauAdminTransportService } from '../services/reseau-admin-transport.service';
import {
  EquipementTransport,
  EquipementTransportCreate,
  EquipementTransportUpdate,
  SourceTransport,
  SourceTransportCreate,
  SourceTransportUpdate,
} from '../../../shared/models/reseau-transport.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

type ReseauTransTab = 'equipements' | 'sources';

@Component({
  selector: 'sir-reseau-transport-admin',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  templateUrl: './reseau-transport-admin.component.html',
  styleUrl: './reseau-transport-admin.component.scss',
})
export class ReseauTransportAdminComponent implements OnInit {
  private readonly reseau = inject(ReseauAdminTransportService);
  private readonly auth = inject(AuthService);

  readonly pageSize = 20;
  readonly activeTab = signal<ReseauTransTab>('equipements');
  readonly equipements = signal<EquipementTransport[]>([]);
  readonly sources = signal<SourceTransport[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);

  readonly equipementForm = signal({
    code: '',
    libelle: '',
    type_equipement: '',
    is_active: true,
  });
  readonly sourceForm = signal({ code: '', libelle: '', is_active: true });

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_DISPATCHING'));

  ngOnInit(): void {
    this.load();
  }

  onTabChange(tab: ReseauTransTab): void {
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
    if (this.activeTab() === 'equipements') {
      this.equipementForm.set({ code: '', libelle: '', type_equipement: '', is_active: true });
    } else {
      this.sourceForm.set({ code: '', libelle: '', is_active: true });
    }
    this.formOpen.set(true);
    this.error.set(null);
  }

  openEditEquipement(item: EquipementTransport): void {
    this.editingId.set(item.id);
    this.equipementForm.set({
      code: item.code,
      libelle: item.libelle,
      type_equipement: item.type_equipement,
      is_active: item.is_active,
    });
    this.formOpen.set(true);
  }

  openEditSource(item: SourceTransport): void {
    this.editingId.set(item.id);
    this.sourceForm.set({
      code: item.code,
      libelle: item.libelle,
      is_active: item.is_active,
    });
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  patchEquipementForm(
    field: 'code' | 'libelle' | 'type_equipement' | 'is_active',
    value: string | boolean,
  ): void {
    this.equipementForm.update((current) => ({ ...current, [field]: value }));
  }

  patchSourceForm(field: 'code' | 'libelle' | 'is_active', value: string | boolean): void {
    this.sourceForm.update((current) => ({ ...current, [field]: value }));
  }

  saveForm(): void {
    if (this.activeTab() === 'equipements') {
      this.saveEquipement();
    } else {
      this.saveSource();
    }
  }

  deactivateEquipement(item: EquipementTransport): void {
    if (!confirm(`Désactiver « ${item.libelle} » ?`)) return;
    this.reseau.deleteEquipement(item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  deactivateSource(item: SourceTransport): void {
    if (!confirm(`Désactiver « ${item.libelle} » ?`)) return;
    this.reseau.deleteSource(item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private saveEquipement(): void {
    const f = this.equipementForm();
    if (!f.code.trim() || !f.libelle.trim() || !f.type_equipement.trim()) {
      this.error.set('Code, libellé et type sont obligatoires.');
      return;
    }
    this.saving.set(true);
    const editId = this.editingId();
    if (editId === null) {
      const body: EquipementTransportCreate = {
        code: f.code.trim(),
        libelle: f.libelle.trim(),
        type_equipement: f.type_equipement.trim(),
      };
      this.reseau.createEquipement(body).subscribe({
        next: () => this.afterSave(),
        error: (err: Error) => this.onSaveError(err),
      });
      return;
    }
    const body: EquipementTransportUpdate = {
      code: f.code.trim(),
      libelle: f.libelle.trim(),
      type_equipement: f.type_equipement.trim(),
      is_active: f.is_active,
    };
    this.reseau.updateEquipement(editId, body).subscribe({
      next: () => this.afterSave(),
      error: (err: Error) => this.onSaveError(err),
    });
  }

  private saveSource(): void {
    const f = this.sourceForm();
    if (!f.code.trim() || !f.libelle.trim()) {
      this.error.set('Code et libellé sont obligatoires.');
      return;
    }
    this.saving.set(true);
    const editId = this.editingId();
    if (editId === null) {
      const body: SourceTransportCreate = {
        code: f.code.trim(),
        libelle: f.libelle.trim(),
      };
      this.reseau.createSource(body).subscribe({
        next: () => this.afterSave(),
        error: (err: Error) => this.onSaveError(err),
      });
      return;
    }
    const body: SourceTransportUpdate = {
      code: f.code.trim(),
      libelle: f.libelle.trim(),
      is_active: f.is_active,
    };
    this.reseau.updateSource(editId, body).subscribe({
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

  private load(): void {
    this.loading.set(true);
    this.error.set(null);
    const params = { page: this.page(), page_size: this.pageSize };

    if (this.activeTab() === 'equipements') {
      this.reseau.listEquipements(params).subscribe({
        next: (res) => {
          this.equipements.set(res.items);
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

    this.reseau.listSources(params).subscribe({
      next: (res) => {
        this.sources.set(res.items);
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
