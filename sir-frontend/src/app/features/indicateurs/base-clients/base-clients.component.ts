import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { AuthService } from '../../../core/auth/auth.service';
import { BaseClientsResume, PeriodeContrats } from '../../../shared/models/base-clients.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { BaseClientsService } from '../services/base-clients.service';

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** Fichier H2MC « nombredeclientsh2mc_MMAAAA.xlsx » : le mois se lit dans le nom. */
const RE_NOM_FICHIER = /(\d{2})(\d{4})\.xlsx$/i;

/**
 * Base clients SAIFI/SAIDI : contrats par unité de relève (BI_ODS chaque jour à 7 h,
 * ou fichier mensuel H2MC), reprise de l'atelier de l'application bureau SIR.
 */
@Component({
  selector: 'sir-base-clients',
  standalone: true,
  imports: [PageHeaderComponent, AnalyticsNavComponent, DatePipe, DecimalPipe],
  templateUrl: './base-clients.component.html',
  styleUrl: './base-clients.component.scss',
})
export class BaseClientsComponent implements OnInit {
  private readonly service = inject(BaseClientsService);
  private readonly auth = inject(AuthService);

  readonly resume = signal<BaseClientsResume | null>(null);
  readonly chargement = signal(true);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly envoi = signal(false);

  readonly fichier = signal<File | null>(null);
  readonly annee = signal(new Date().getFullYear());
  readonly mois = signal(new Date().getMonth() + 1);

  readonly moisLibelles = MOIS;
  readonly annees = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i);

  readonly dernier = computed<PeriodeContrats | null>(() => this.resume()?.periodes[0] ?? null);
  readonly liensValides = computed(() => this.resume()?.liens['valide'] ?? 0);
  readonly liensEnAttente = computed(() => {
    const liens = this.resume()?.liens ?? {};
    return (liens['ajout_propose'] ?? 0) + (liens['suppression_proposee'] ?? 0);
  });

  ngOnInit(): void {
    this.charger();
  }

  peutAdministrer(): boolean {
    return this.auth.hasRole('ADMIN_SCR', 'ADMIN_SAQS');
  }

  libelleMois(p: PeriodeContrats): string {
    return `${MOIS[p.mois - 1]} ${p.annee}`;
  }

  /** Part des contrats du mois rattachés à au moins un poste (base réelle de SAIFI/SAIDI). */
  couverture(p: PeriodeContrats): number {
    return p.contrats ? Math.round((p.contrats_rattaches / p.contrats) * 1000) / 10 : 0;
  }

  charger(): void {
    this.chargement.set(true);
    this.service.getResume().subscribe({
      next: (res) => {
        this.resume.set(res);
        this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
  }

  synchroniser(): void {
    this.lancer(() => this.service.synchroniser());
  }

  choisirFichier(event: Event): void {
    const input = event.target as HTMLInputElement;
    const f = input.files?.[0] ?? null;
    this.fichier.set(f);
    const m = f ? RE_NOM_FICHIER.exec(f.name) : null;
    if (m) {
      const mois = Number(m[1]);
      if (mois >= 1 && mois <= 12) {
        this.mois.set(mois);
        this.annee.set(Number(m[2]));
      }
    }
  }

  importer(): void {
    const f = this.fichier();
    if (!f) return;
    this.lancer(() => this.service.importer(f, this.annee(), this.mois()), () => this.fichier.set(null));
  }

  private lancer(
    appel: () => ReturnType<BaseClientsService['synchroniser']>,
    apres?: () => void,
  ): void {
    this.envoi.set(true);
    this.erreur.set(null);
    this.message.set(null);
    appel().subscribe({
      next: (res) => {
        this.envoi.set(false);
        this.message.set(`${res.message}. Les clients des postes et la base SAIFI/SAIDI seront à jour dans quelques minutes.`);
        apres?.();
        setTimeout(() => this.charger(), 15000);
      },
      error: (err: Error) => {
        this.envoi.set(false);
        this.erreur.set(err.message);
      },
    });
  }
}
