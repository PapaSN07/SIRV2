import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { combineLatest, debounceTime, map } from 'rxjs';
import { AuthService } from '../../../core/auth/auth.service';
import { LocalisationSuivi } from '../../../shared/models/suivi-incidents.models';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { KpiComponent } from '../../../shared/ui/kpi/kpi.component';
import { formatEntier, formatPart } from '../../../shared/utils/formats-indicateurs';
import { Etat, charger, filtresResolus$ } from '../services/chargement';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';

const TAILLE_PAGE = 20;
/** Rôles qui ouvrent Administration → Schémas unifilaires (route `admin/schemas-unifilaires`). */
const ROLES_RAPPROCHEMENT = ['ADMIN_SCR', 'ADMIN_SAQS', 'BCC', 'BRC', 'SUPERVISEUR'];

/**
 * Onglet « Localisation » : part des postes touchés placés sur la carte SIG, détail par poste
 * source et liste des postes non localisés, à corriger dans le rapprochement Schéma / SIG / SIR.
 */
@Component({
  selector: 'sir-suivi-localisation',
  standalone: true,
  imports: [EtatComponent, KpiComponent, RouterLink],
  templateUrl: './localisation.component.html',
  styleUrl: './localisation.component.scss',
})
export class LocalisationComponent {
  private readonly api = inject(SuiviIncidentsService);
  private readonly auth = inject(AuthService);
  readonly f = inject(SuiviIncidentsFiltresService);
  readonly formatEntier = formatEntier;
  readonly formatPart = formatPart;

  readonly etat = signal<Etat<LocalisationSuivi>>({ type: 'chargement' });
  readonly page = signal(1);
  private readonly relance = signal(0);
  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  /** Accès à l'écran du rapprochement (rôles de la route ou permission des rôles créés). */
  readonly voitRapprochement = computed(
    () => this.auth.hasRole(...ROLES_RAPPROCHEMENT) || this.auth.hasPermission('interruptions_distribution:read'),
  );
  /** Seul l'Admin SCR associe les postes dans l'écran du rapprochement. */
  readonly peutCorriger = computed(() => this.auth.hasRole('ADMIN_SCR'));
  private derniersFiltres = '';
  private changementDePage = false;

  constructor() {
    const filtres$ = filtresResolus$(this.filtresResolus);
    // Nouveaux filtres : retour à la première page
    filtres$.pipe(takeUntilDestroyed()).subscribe(() => this.page.set(1));
    charger(
      // debounceTime(0) : nouveaux filtres + retour en page 1 = une seule requête
      combineLatest([filtres$, toObservable(this.page), toObservable(this.relance)]).pipe(
        debounceTime(0),
        map(([x, p]) => {
          // Calculé avant l'état « chargement » (que charger() émet avant l'appel)
          const empreinte = JSON.stringify(x);
          this.changementDePage = empreinte === this.derniersFiltres && this.etat().type === 'ok';
          this.derniersFiltres = empreinte;
          return { x, p };
        }),
      ),
      ({ x, p }) => this.api.getLocalisation(x, p, TAILLE_PAGE),
      (e) => {
        // Simple changement de page : l'écran reste affiché pendant le chargement
        if (e.type === 'chargement' && this.changementDePage) return;
        this.etat.set(e);
      },
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly donnees = computed(() => {
    const e = this.etat();
    return e.type === 'ok' ? e.donnees : null;
  });

  readonly nombrePages = computed(() => {
    const n = this.donnees()?.non_localises;
    return n ? Math.max(1, Math.ceil(n.total / n.size)) : 1;
  });

  allerPage(p: number): void {
    const cible = Math.min(Math.max(1, p), this.nombrePages());
    if (cible !== this.page()) this.page.set(cible);
  }

  filtrerPosteSource(id: number | null, libelle?: string): void {
    if (id !== null) this.f.definir({ poste_source_id: id }, libelle);
  }

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }
}
