import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { PageHeaderComponent } from '../../shared/ui/page-header/page-header.component';
import { BarreFiltresComponent } from './barre-filtres/barre-filtres.component';
import { SuiviIncidentsFiltresService, modePeriode } from './services/suivi-incidents-filtres.service';
import { dateCourte, jourMois, libelleSemaine, semaineSenelec } from '../../shared/utils/semaine-senelec';

export interface OngletSuivi {
  chemin: string;
  libelle: string;
  icone: string;
}

/** Onglets du menu (routes enfants : lien partageable, F5 garde l'onglet). */
export const ONGLETS_SUIVI: OngletSuivi[] = [
  { chemin: 'vue-ensemble', libelle: 'Vue d’ensemble', icone: 'space_dashboard' },
  { chemin: 'carte', libelle: 'Carte', icone: 'map' },
  { chemin: 'evolution', libelle: 'Évolution', icone: 'show_chart' },
  { chemin: 'reseau', libelle: 'Réseau', icone: 'account_tree' },
  { chemin: 'saifi-saidi', libelle: 'SAIFI / SAIDI', icone: 'speed' },
  { chemin: 'localisation', libelle: 'Localisation', icone: 'location_on' },
];

/**
 * Menu « Suivi incidents » : tableau de bord des interruptions (fusion de l'application
 * Suivi incidents SIR). La barre de filtres et son état sont communs à tous les onglets ;
 * le service de filtres est fourni ici, une instance par visite du menu.
 */
@Component({
  selector: 'sir-suivi-incidents',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, PageHeaderComponent, BarreFiltresComponent],
  providers: [SuiviIncidentsFiltresService],
  template: `
    <div class="suivi">
      <sir-page-header title="Suivi incidents" [breadcrumbs]="[{ label: 'Analyse' }, { label: 'Suivi incidents' }]" />

      <div id="suivi-filtres" class="suivi__filtres">
        <sir-barre-filtres />
      </div>

      <!-- Zone collante : onglets + rappel des filtres (la barre complète reste en haut) -->
      <div class="suivi__barre-collante">
        <nav class="sir-tabs suivi__onglets" aria-label="Vues du suivi des incidents">
          @for (o of onglets; track o.chemin) {
            <a
              class="sir-tab"
              [routerLink]="o.chemin"
              queryParamsHandling="preserve"
              routerLinkActive="sir-tab--active"
              ariaCurrentWhenActive="page"
            >
              <span class="material-symbols-outlined" aria-hidden="true">{{ o.icone }}</span>
              {{ o.libelle }}
            </a>
          }
        </nav>
        <button type="button" class="suivi__rappel" (click)="allerAuxFiltres()" aria-controls="suivi-filtres">
          <span class="material-symbols-outlined" aria-hidden="true">tune</span>
          {{ rappelFiltres() }}
        </button>
      </div>

      <section class="suivi__contenu" aria-label="Contenu de l’onglet">
        <router-outlet />
      </section>
    </div>
  `,
  styleUrl: './suivi-incidents.component.scss',
})
export class SuiviIncidentsComponent {
  private readonly filtres = inject(SuiviIncidentsFiltresService);
  readonly onglets = ONGLETS_SUIVI;

  /** « S47 · 14/11 → 20/11/2026 · 2 filtres » : rappel quand la barre complète est hors de vue. */
  readonly rappelFiltres = computed(() => {
    const { debut, fin } = this.filtres.filtres();
    const mode = modePeriode(debut, fin);
    const periode =
      mode === 'semaine' ? libelleSemaine(semaineSenelec(debut)) : `${jourMois(debut)} → ${dateCourte(fin)}`;
    const n = this.filtres.actifs().length;
    return n === 0 ? periode : `${periode} · ${n} filtre${n > 1 ? 's' : ''}`;
  });

  allerAuxFiltres(): void {
    const zone = document.getElementById('suivi-filtres');
    zone?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    zone?.querySelector<HTMLElement>('button, select, input')?.focus({ preventScroll: true });
  }
}
