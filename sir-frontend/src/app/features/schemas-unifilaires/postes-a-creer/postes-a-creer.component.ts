import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../../core/auth/auth.service';
import { PosteACreer, StatutPosteACreer } from '../../../shared/models/schema-unifilaire.models';
import { SchemaUnifilaireService } from '../schema-unifilaire.service';

/** Décision en cours sur une proposition : validation (code facultatif) ou rejet (motif). */
interface Decision {
  demande: PosteACreer;
  action: 'valider' | 'rejeter';
  texte: string;
}

const TAILLE_PAGE = 50;

/** Postes à créer dans SIR, proposés depuis le rapprochement : validation ou rejet par l'Admin SCR. */
@Component({
  selector: 'sir-postes-a-creer',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule],
  templateUrl: './postes-a-creer.component.html',
  styleUrl: '../schema-rapprochement/schema-rapprochement.component.scss',
})
export class PostesACreerComponent {
  private readonly service = inject(SchemaUnifilaireService);
  private readonly auth = inject(AuthService);

  readonly statut = signal<StatutPosteACreer>('propose');
  readonly demandes = signal<PosteACreer[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly chargement = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly message = signal<string | null>(null);
  readonly decision = signal<Decision | null>(null);
  readonly envoi = signal(false);

  readonly canValider = computed(() => {
    this.auth.currentUser();
    return this.auth.hasRole('ADMIN_SCR');
  });
  readonly pages = computed(() => Math.max(1, Math.ceil(this.total() / TAILLE_PAGE)));
  readonly onglets: { id: StatutPosteACreer; libelle: string }[] = [
    { id: 'propose', libelle: 'À valider' },
    { id: 'valide', libelle: 'Créés' },
    { id: 'rejete', libelle: 'Rejetés' },
  ];

  constructor() {
    this.charger();
  }

  charger(): void {
    this.chargement.set(true);
    this.erreur.set(null);
    this.service.postesACreer(this.statut(), this.page(), TAILLE_PAGE).subscribe({
      next: (res) => {
        this.demandes.set(res.items);
        this.total.set(res.total);
        this.chargement.set(false);
      },
      error: (err: Error) => {
        this.erreur.set(err.message);
        this.chargement.set(false);
      },
    });
  }

  choisirStatut(statut: StatutPosteACreer): void {
    this.statut.set(statut);
    this.page.set(1);
    this.charger();
  }

  allerPage(page: number): void {
    if (page < 1 || page > this.pages()) return;
    this.page.set(page);
    this.charger();
  }

  ouvrir(demande: PosteACreer, action: 'valider' | 'rejeter'): void {
    this.decision.set({ demande, action, texte: '' });
  }

  onTexte(valeur: string): void {
    const d = this.decision();
    if (d) this.decision.set({ ...d, texte: valeur });
  }

  confirmer(): void {
    const d = this.decision();
    if (!d || this.envoi()) return;
    if (d.action === 'rejeter' && d.texte.trim().length < 3) return;
    this.envoi.set(true);
    const appel =
      d.action === 'valider'
        ? this.service.validerPoste(d.demande.id, d.texte.trim() || null)
        : this.service.rejeterPoste(d.demande.id, d.texte.trim());
    appel.subscribe({
      next: (res) => {
        this.envoi.set(false);
        this.decision.set(null);
        this.message.set(
          d.action === 'valider'
            ? `Poste « ${res.libelle} » créé dans SIR (code ${res.poste_code ?? '—'}) et relié au schéma.`
            : `Proposition « ${res.libelle} » rejetée.`,
        );
        this.charger();
      },
      error: (err: Error) => {
        this.envoi.set(false);
        this.erreur.set(err.message);
      },
    });
  }
}
