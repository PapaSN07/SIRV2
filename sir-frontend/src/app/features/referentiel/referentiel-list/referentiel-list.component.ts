import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { FONCTIONNALITES } from '../../../core/config/fonctionnalites';
import { ReferentielService } from '../services/referentiel.service';
import {
  ReferentielCreate,
  ReferentielItem,
  ReferentielResource,
  ReferentielUpdate,
  StatutReferentiel,
  TypeReseau,
} from '../../../shared/models/referentiel.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';
import { PaginatorComponent } from '../../../shared/ui/paginator/paginator.component';

interface ReferentielTab {
  key: ReferentielResource;
  label: string;
  filterType: boolean;
  icon: string;
  aide: string;
}

const TABS: ReferentielTab[] = [
  { key: 'causes', label: 'Causes', filterType: true, icon: 'report', aide: 'Causes des interruptions (saisie, rapports, indicateurs).' },
  { key: 'sieges', label: 'Sièges', filterType: true, icon: 'location_on', aide: 'Siège du défaut sur le réseau (câble, cellule, transformateur…).' },
  { key: 'signalisations', label: 'Signalisations', filterType: true, icon: 'notification_important', aide: 'Protections et signalisations relevées au déclenchement.' },
  { key: 'natures', label: 'Natures', filterType: false, icon: 'category', aide: 'Nature de l\'interruption (permanent, fugitif, travaux…).' },
  { key: 'types_end', label: 'Types de rapport', filterType: false, icon: 'assessment', aide: 'Classement de l\'END dans les rapports (incident, travaux, délestage…).' },
  { key: 'entreprises', label: 'Entreprises', filterType: false, icon: 'domain', aide: 'Entreprises intervenant sur le réseau.' },
  { key: 'prestataires', label: 'Prestataires', filterType: false, icon: 'engineering', aide: 'Prestataires de travaux.' },
];

interface ReferentielFormState {
  code: string;
  libelle: string;
  type_reseau: TypeReseau | '';
  description: string;
  is_active: boolean;
}

@Component({
  selector: 'sir-referentiel-list',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent, PaginatorComponent],
  templateUrl: './referentiel-list.component.html',
  styleUrl: './referentiel-list.component.scss',
})
export class ReferentielListComponent implements OnInit {
  readonly transport = FONCTIONNALITES.transport;
  private readonly referentiel = inject(ReferentielService);
  private readonly auth = inject(AuthService);

  readonly tabs = TABS;
  readonly pageSize = 20;

  readonly activeTabIndex = signal(0);
  readonly activeTab = computed(() => this.tabs[this.activeTabIndex()]);
  readonly items = signal<ReferentielItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly typeReseau = signal<TypeReseau | null>(null);
  readonly statut = signal<StatutReferentiel>('tous');
  readonly recherche = signal('');
  readonly tri = signal<string>('libelle');
  private delaiRecherche: ReturnType<typeof setTimeout> | null = null;
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly formOpen = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly form = signal<ReferentielFormState>(this.emptyForm());

  readonly canWrite = computed(() => this.auth.hasRole('ADMIN_SCR', 'ADMIN_DISPATCHING'));

  ngOnInit(): void {
    this.load();
  }

  onTabChange(index: number): void {
    this.activeTabIndex.set(index);
    this.page.set(1);
    this.typeReseau.set(null);
    this.recherche.set('');
    this.closeForm();
    this.load();
  }

  /** Recherche à la frappe (300 ms après la dernière touche), depuis la première page. */
  onRecherche(texte: string): void {
    this.recherche.set(texte);
    if (this.delaiRecherche) clearTimeout(this.delaiRecherche);
    this.delaiRecherche = setTimeout(() => {
      this.page.set(1);
      this.load();
    }, 300);
  }

  onStatutChange(value: string): void {
    this.statut.set((value as StatutReferentiel) || 'tous');
    this.page.set(1);
    this.load();
  }

  /** Clic sur un en-tête : tri croissant, puis décroissant. */
  trier(colonne: string): void {
    this.tri.set(this.tri() === colonne ? '-' + colonne : colonne);
    this.page.set(1);
    this.load();
  }

  iconeTri(colonne: string): string {
    if (this.tri() === colonne) return 'arrow_upward';
    if (this.tri() === '-' + colonne) return 'arrow_downward';
    return 'unfold_more';
  }

  libelleType(type: TypeReseau | null): string {
    return type === 'distribution' ? 'Distribution' : type === 'transport' ? 'Transport' : type === 'commun' ? 'Commun' : '—';
  }

  reactivate(item: ReferentielItem): void {
    this.referentiel
      .update(this.activeTab().key, item.id, {
        code: item.code,
        libelle: item.libelle,
        type_reseau: item.type_reseau,
        description: item.description,
        is_active: true,
      })
      .subscribe({
        next: () => this.load(),
        error: (err: Error) => this.error.set(err.message),
      });
  }

  onTypeChange(value: string): void {
    this.typeReseau.set(value ? (value as TypeReseau) : null);
    this.page.set(1);
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

  openEdit(item: ReferentielItem): void {
    this.editingId.set(item.id);
    this.form.set({
      code: item.code,
      libelle: item.libelle,
      type_reseau: item.type_reseau ?? '',
      description: item.description ?? '',
      is_active: item.is_active,
    });
    this.formOpen.set(true);
    this.error.set(null);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
    this.form.set(this.emptyForm());
  }

  patchForm(field: keyof ReferentielFormState, value: string | boolean): void {
    this.form.update((current) => ({ ...current, [field]: value }));
  }

  saveForm(): void {
    const state = this.form();
    if (!state.code.trim() || !state.libelle.trim()) {
      this.error.set('Code et libellé sont obligatoires.');
      return;
    }

    this.saving.set(true);
    this.error.set(null);
    const tab = this.activeTab();
    const typeReseau = tab.filterType && state.type_reseau ? state.type_reseau : null;

    const editId = this.editingId();
    if (editId === null) {
      const body: ReferentielCreate = {
        code: state.code.trim(),
        libelle: state.libelle.trim(),
        type_reseau: typeReseau,
        description: state.description.trim() || null,
      };
      this.referentiel.create(tab.key, body).subscribe({
        next: () => {
          this.saving.set(false);
          this.closeForm();
          this.load();
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.saving.set(false);
        },
      });
      return;
    }

    const body: ReferentielUpdate = {
      code: state.code.trim(),
      libelle: state.libelle.trim(),
      type_reseau: typeReseau,
      description: state.description.trim() || null,
      is_active: state.is_active,
    };
    this.referentiel.update(tab.key, editId, body).subscribe({
      next: () => {
        this.saving.set(false);
        this.closeForm();
        this.load();
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.saving.set(false);
      },
    });
  }

  deactivate(item: ReferentielItem): void {
    if (!confirm(`Désactiver « ${item.libelle} » ?`)) return;
    this.referentiel.delete(this.activeTab().key, item.id).subscribe({
      next: () => this.load(),
      error: (err: Error) => this.error.set(err.message),
    });
  }

  private load(): void {
    const tab = this.activeTab();
    this.loading.set(true);
    this.error.set(null);

    this.referentiel
      .list(tab.key, {
        page: this.page(),
        page_size: this.pageSize,
        type_reseau: tab.filterType ? (this.typeReseau() ?? undefined) : undefined,
        statut: this.statut(),
        q: this.recherche(),
        tri: this.tri(),
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

  private emptyForm(): ReferentielFormState {
    return { code: '', libelle: '', type_reseau: '', description: '', is_active: true };
  }
}
