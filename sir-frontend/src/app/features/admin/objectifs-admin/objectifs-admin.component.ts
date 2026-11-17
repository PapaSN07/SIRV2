import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AdminAdvancedService } from '../services/admin-advanced.service';
import { ObjectifsLigne } from '../../../shared/models/admin.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AdminNavComponent } from '../../../shared/ui/admin-nav/admin-nav.component';

type Champ = 'end_mwh' | 'saifi' | 'saidi' | 'defauts_100km';

interface LigneSaisie {
  region_id: number | null;
  libelle: string;
  valeurs: Record<Champ, string>;
  modifiee: boolean;
}

const CHAMPS: { cle: Champ; libelle: string; unite: string; pas: string }[] = [
  { cle: 'end_mwh', libelle: 'END HTA', unite: 'MWh', pas: '0.01' },
  { cle: 'saifi', libelle: 'SAIFI', unite: 'interruptions / client', pas: '0.001' },
  { cle: 'saidi', libelle: 'SAIDI', unite: 'heures / client', pas: '0.001' },
  { cle: 'defauts_100km', libelle: 'Défauts aux 100 km', unite: 'défauts', pas: '0.01' },
];

/** Administration → Objectifs : objectifs annuels nationaux et par région (lus par le tableau de bord). */
@Component({
  selector: 'sir-objectifs-admin',
  standalone: true,
  imports: [FormsModule, PageHeaderComponent, AdminNavComponent],
  template: `
    <section class="admin-page">
      <sir-page-header
        title="Objectifs annuels"
        [breadcrumbs]="[{ label: 'Tableau de bord', route: '/' }, { label: 'Administration' }, { label: 'Objectifs' }]"
      >
        <div actions class="annee">
          <label for="annee-objectifs">Année</label>
          <select id="annee-objectifs" class="sir-select" [ngModel]="annee()" (ngModelChange)="changerAnnee(+$event)">
            @for (a of annees; track a) {
              <option [value]="a">{{ a }}</option>
            }
          </select>
        </div>
      </sir-page-header>

      <sir-admin-nav />

      <div class="sir-card">
        <div class="intro">
          <span class="material-symbols-outlined" aria-hidden="true">info</span>
          <p>
            Les objectifs sont annuels. Le tableau de bord les répartit au jour (objectif ÷ jours de l'année) et compare le
            réalisé cumulé à la part d'objectif déjà écoulée. Une région sans objectif reprend l'objectif national.
          </p>
        </div>

        @if (erreur()) {
          <p class="alerte alerte--erreur" role="alert">{{ erreur() }}</p>
        }
        @if (message()) {
          <p class="alerte alerte--ok" role="status">{{ message() }}</p>
        }

        @if (chargement()) {
          <p class="vide">Chargement…</p>
        } @else {
          <div class="table-wrap">
            <table class="sir-table">
              <thead>
                <tr>
                  <th>Périmètre</th>
                  @for (c of champs; track c.cle) {
                    <th>{{ c.libelle }} <span class="unite">({{ c.unite }})</span></th>
                  }
                  <th class="col-actions"><span class="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                @for (ligne of lignes(); track ligne.libelle; let i = $index) {
                  <tr [class.modifiee]="ligne.modifiee">
                    <td>
                      <span class="perimetre">
                        <span class="material-symbols-outlined" aria-hidden="true">{{ ligne.region_id === null ? 'public' : 'location_on' }}</span>
                        {{ ligne.libelle }}
                      </span>
                    </td>
                    @for (c of champs; track c.cle) {
                      <td>
                        <input
                          class="saisie"
                          type="number"
                          min="0"
                          [step]="c.pas"
                          [attr.aria-label]="c.libelle + ' ' + ligne.libelle"
                          [placeholder]="ligne.region_id === null ? '—' : 'national'"
                          [ngModel]="ligne.valeurs[c.cle]"
                          (ngModelChange)="saisir(i, c.cle, $event)"
                        />
                      </td>
                    }
                    <td class="col-actions">
                      <button
                        type="button"
                        class="sir-btn sir-btn--primary sir-btn--sm"
                        [disabled]="!ligne.modifiee || enregistrement() === i"
                        (click)="enregistrer(i)"
                      >
                        <span class="material-symbols-outlined" aria-hidden="true">save</span>
                        {{ enregistrement() === i ? 'Enregistrement…' : 'Enregistrer' }}
                      </button>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        }
      </div>
    </section>
  `,
  styles: [
    `
      .admin-page { max-width: 1400px; margin: 0 auto; }
      .annee { display: flex; align-items: center; gap: 0.5rem; font-size: 13px; font-weight: 600; color: #6b6580; }
      .intro { display: flex; gap: 0.75rem; align-items: flex-start; padding: 1rem 1.25rem; border-bottom: 1px solid #ede9f5; color: #403a52; font-size: 13px; line-height: 20px; }
      .intro p { margin: 0; }
      .intro .material-symbols-outlined { color: #5b2a9e; font-size: 20px; }
      .table-wrap { overflow-x: auto; }
      .unite { font-weight: 500; text-transform: none; letter-spacing: 0; color: #8b85a0; }
      .perimetre { display: flex; align-items: center; gap: 0.5rem; font-weight: 600; color: #262051; white-space: nowrap; }
      .perimetre .material-symbols-outlined { font-size: 18px; color: #5b2a9e; }
      .saisie { width: 100%; min-width: 110px; height: 2.25rem; padding: 0 0.6rem; border: 1px solid #dad6e4; border-radius: 8px; font: inherit; font-size: 14px; font-variant-numeric: tabular-nums; }
      .saisie:focus { outline: none; border-color: #5b2a9e; box-shadow: 0 0 0 3px rgba(91, 42, 158, 0.18); }
      tr.modifiee { background: #faf7ff; }
      .alerte { margin: 1rem 1.25rem 0; padding: 0.65rem 0.9rem; border-radius: 8px; font-size: 13px; }
      .alerte--erreur { background: #fdecec; color: #b42328; }
      .alerte--ok { background: #e9f6ef; color: #16794f; }
      .vide { padding: 2rem; text-align: center; color: #6b6580; }
      .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
    `,
  ],
})
export class ObjectifsAdminComponent implements OnInit {
  private readonly admin = inject(AdminAdvancedService);

  readonly champs = CHAMPS;
  readonly annees = [new Date().getFullYear() + 1, new Date().getFullYear(), new Date().getFullYear() - 1];
  readonly annee = signal(new Date().getFullYear());
  readonly lignes = signal<LigneSaisie[]>([]);
  readonly chargement = signal(false);
  readonly enregistrement = signal<number | null>(null);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  ngOnInit(): void {
    this.charger();
  }

  changerAnnee(annee: number): void {
    this.annee.set(annee);
    this.charger();
  }

  saisir(index: number, champ: Champ, valeur: string | number | null): void {
    this.message.set(null);
    this.lignes.update((lignes) =>
      lignes.map((l, i) =>
        i === index ? { ...l, modifiee: true, valeurs: { ...l.valeurs, [champ]: valeur === null ? '' : String(valeur) } } : l,
      ),
    );
  }

  enregistrer(index: number): void {
    const ligne = this.lignes()[index];
    const valeurs: Partial<Record<Champ, number>> = {};
    for (const c of CHAMPS) {
      const brut = ligne.valeurs[c.cle].trim();
      if (!brut) continue;
      const n = Number(brut.replace(',', '.'));
      if (!Number.isFinite(n) || n < 0) {
        this.erreur.set(`${c.libelle} : saisissez un nombre positif ou nul.`);
        return;
      }
      valeurs[c.cle] = n;
    }
    if (Object.keys(valeurs).length === 0) {
      this.erreur.set('Saisissez au moins un objectif.');
      return;
    }
    this.erreur.set(null);
    this.enregistrement.set(index);
    this.admin.saveObjectifs({ annee: this.annee(), region_id: ligne.region_id, ...valeurs }).subscribe({
      next: (res) => {
        this.appliquer(res.lignes);
        this.enregistrement.set(null);
        this.message.set(`Objectifs ${this.annee()} enregistrés pour ${ligne.libelle}.`);
      },
      error: (err: Error) => {
        this.enregistrement.set(null);
        this.erreur.set(err.message);
      },
    });
  }

  private charger(): void {
    this.chargement.set(true);
    this.erreur.set(null);
    this.message.set(null);
    this.admin.getObjectifs(this.annee()).subscribe({
      next: (res) => {
        this.appliquer(res.lignes);
        this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
  }

  private appliquer(lignes: ObjectifsLigne[]): void {
    const texte = (v: number | null) => (v === null || v === undefined ? '' : String(v));
    this.lignes.set(
      lignes.map((l) => ({
        region_id: l.region_id,
        libelle: l.libelle,
        modifiee: false,
        valeurs: {
          end_mwh: texte(l.end_mwh),
          saifi: texte(l.saifi),
          saidi: texte(l.saidi),
          defauts_100km: texte(l.defauts_100km),
        },
      })),
    );
  }
}
