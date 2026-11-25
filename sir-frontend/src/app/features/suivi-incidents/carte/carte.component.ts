import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed, toObservable } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { combineLatest, map } from 'rxjs';
import { CarteSuivi, PointCarte } from '../../../shared/models/suivi-incidents.models';
import { EtatComponent } from '../../../shared/ui/etat/etat.component';
import { formatDuree, formatEntier, formatPart } from '../../../shared/utils/formats-indicateurs';
import { Etat, charger, filtresResolus$ } from '../services/chargement';
import { SuiviIncidentsFiltresService } from '../services/suivi-incidents-filtres.service';
import { SuiviIncidentsService } from '../services/suivi-incidents.service';
import { CarteIncidentsComponent } from './carte-incidents.component';

/**
 * Onglet « Carte » : postes touchés sur la période, placés par le rapprochement SIG ou par
 * leur nom. Le nombre de postes non placés est toujours dit, avec un lien vers l'onglet
 * Localisation.
 */
@Component({
  selector: 'sir-suivi-carte',
  standalone: true,
  imports: [EtatComponent, CarteIncidentsComponent, RouterLink],
  template: `
    <section class="sir-card carte-suivi" aria-labelledby="titre-carte">
      <div class="carte-suivi__entete">
        <h2 id="titre-carte" class="carte-suivi__titre">Postes touchés</h2>
        @if (donnees(); as d) {
          @if (d.postes_touches) {
          <p class="carte-suivi__compte" aria-live="polite">
            {{ formatEntier(d.postes_localises) }} placés sur {{ formatEntier(d.postes_touches) }}
            ({{ formatPart(taux()) }})
            @if (d.postes_touches > d.postes_localises) {
              ·
              <a routerLink="../localisation" queryParamsHandling="preserve">
                {{ formatEntier(d.postes_touches - d.postes_localises) }} non localisés
              </a>
            }
          </p>
          }
        }
      </div>
      @if (donnees()?.tronque) {
        <p class="carte-suivi__note" role="note">
          Seuls les {{ formatEntier(donnees()!.points.length) }} postes les plus touchés sont affichés : réduisez la
          période ou filtrez par poste source pour voir les autres.
        </p>
      }

      @switch (etat().type) {
        @case ('chargement') {
          <sir-etat type="chargement" hauteur="520px" />
        }
        @case ('erreur') {
          <sir-etat type="erreur" [message]="$any(etat()).message" (reessayer)="reessayer()" />
        }
        @case ('ok') {
          @if (!donnees()!.postes_touches) {
            <sir-etat
              type="vide"
              message="Aucun poste touché sur la période et les filtres choisis."
              [actionVide]="f.effacables().length ? 'Effacer les filtres' : null"
              (action)="f.toutEffacer()"
            />
          } @else if (!donnees()!.points.length) {
            <sir-etat type="vide" message="Aucun poste touché n’a pu être placé sur la carte : voyez l’onglet Localisation." />
          } @else {
            <sir-carte-incidents
              [points]="donnees()!.points"
              [titre]="'Carte des ' + donnees()!.points.length + ' postes touchés placés'"
              (filtrerPoste)="filtrerFeeder($event)"
            />
            <p class="carte-suivi__aide">
              Cliquez sur une bulle pour le détail du poste ; « Filtrer sur ce feeder » applique le filtre à tout le menu.
            </p>
            <details class="carte-suivi__liste">
              <summary>
                <span class="material-symbols-outlined carte-suivi__chevron" aria-hidden="true">expand_more</span>
                Liste des postes placés ({{ formatEntier(donnees()!.points.length) }})
              </summary>
              <div class="carte-suivi__defilement">
                <table class="sir-table carte-suivi__table">
                  <caption class="sr-only">Postes placés sur la carte, du plus touché au moins touché</caption>
                  <thead>
                    <tr>
                      <th scope="col">Poste</th>
                      <th scope="col" class="num">Interruptions</th>
                      <th scope="col" class="num secondaire">Durée cumulée</th>
                      <th scope="col" class="num secondaire">Clients coupés</th>
                      <th scope="col" class="secondaire">Nature dominante</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (p of pointsPage(); track p.poste_id) {
                      <tr>
                        <th scope="row">
                          {{ p.libelle }}
                          <span class="carte-suivi__sous">
                            {{ p.code }}
                            @if (p.feeder_id !== null) {
                              ·
                              <button type="button" class="carte-suivi__lien" (click)="filtrerFeeder(p)" [attr.aria-label]="'Filtrer sur le feeder ' + p.feeder">
                                {{ p.feeder }}
                              </button>
                            }
                          </span>
                        </th>
                        <td class="num">{{ formatEntier(p.nombre) }}</td>
                        <td class="num secondaire">{{ formatDuree(p.duree_heures) }}</td>
                        <td class="num secondaire">{{ formatEntier(p.clients) }}</td>
                        <td class="secondaire">{{ libelleNature[p.nature_dominante] }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
              @if (pointsPage().length < donnees()!.points.length) {
                <button type="button" class="sir-btn sir-btn--ghost sir-btn--sm" (click)="voirPlus()">
                  Afficher 50 postes de plus
                </button>
              }
            </details>
          }
        }
      }
    </section>
  `,
  styleUrl: './carte.component.scss',
})
export class CarteComponent {
  private readonly api = inject(SuiviIncidentsService);
  readonly f = inject(SuiviIncidentsFiltresService);
  readonly formatEntier = formatEntier;
  readonly formatPart = formatPart;
  readonly formatDuree = formatDuree;
  readonly libelleNature: Record<string, string> = {
    incident: 'Incidents',
    delestage: 'Délestages',
    travaux: 'Travaux',
    autre: 'Autres coupures',
  };
  /** Lignes affichées dans la liste (par 50 : jusqu'à 3 000 postes). */
  readonly nbLignes = signal(50);

  readonly etat = signal<Etat<CarteSuivi>>({ type: 'chargement' });
  private readonly relance = signal(0);
  private readonly filtresResolus = computed(() => this.f.resolus()?.filtres ?? null);

  constructor() {
    charger(
      combineLatest([filtresResolus$(this.filtresResolus), toObservable(this.relance)]).pipe(map(([x]) => x)),
      (x) => this.api.getCarte(x),
      (e) => {
        this.etat.set(e);
        this.nbLignes.set(50);
      },
    )
      .pipe(takeUntilDestroyed())
      .subscribe();
  }

  readonly donnees = computed(() => {
    const e = this.etat();
    return e.type === 'ok' ? e.donnees : null;
  });

  readonly pointsPage = computed(() => (this.donnees()?.points ?? []).slice(0, this.nbLignes()));

  voirPlus(): void {
    this.nbLignes.update((n) => n + 50);
  }

  readonly taux = computed(() => {
    const d = this.donnees();
    return d && d.postes_touches ? d.postes_localises / d.postes_touches : 0;
  });

  filtrerFeeder(p: PointCarte): void {
    if (p.feeder_id !== null) this.f.definir({ feeder_id: p.feeder_id }, p.feeder);
  }

  reessayer(): void {
    this.relance.update((n) => n + 1);
  }
}
