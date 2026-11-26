import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AuthService } from '../../../core/auth/auth.service';
import { CategorieFis } from '../../../shared/models/correspondance-fis.models';
import { FisImportResponse } from '../../../shared/models/interruption.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';

type Etape = 'choix' | 'apercu' | 'termine';

/** Libellé FIS non reconnu, extrait d'un motif de rejet (lien pré-rempli pour l'Admin SCR). */
interface LibelleNonReconnu {
  categorie: CategorieFis;
  nomCategorie: string;
  libelle: string;
}

/** Motif de rejet lié au Référentiel ou à une correspondance FIS. */
/** Rejets réglables par une correspondance FIS (pas « Feeder … ambigu : N correspondances exactes »). */
const MOTIF_REFERENTIEL = /dans le r[ée]f[ée]rentiel|correspondance FIS/i;
/** « Ligne N°… : Cause « xxx » : aucune entrée active … » (message de fis_import_service). */
const MOTIF_LIBELLE_INCONNU = /(Nature|Cause|Siège|Signalisation) « (.+?) » : aucune entrée active/;
const CATEGORIES: Record<string, CategorieFis> = {
  Nature: 'nature',
  Cause: 'cause',
  Siège: 'siege',
  Signalisation: 'signalisation',
};

/**
 * Import d'un fichier FIS en deux temps : aperçu (contrôle sans enregistrement),
 * puis import confirmé. Les lignes rejetées sont listées avec leur motif.
 */
@Component({
  selector: 'sir-fis-import',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe, PageHeaderComponent],
  templateUrl: './fis-import.component.html',
  styleUrl: './fis-import.component.scss',
})
export class FisImportComponent {
  private readonly service = inject(InterruptionDistributionService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  /** Lien direct vers les correspondances FIS : Admin SCR (et SUPERADMIN). */
  readonly peutGererCorrespondances = computed(() => this.auth.hasRole('ADMIN_SCR'));

  readonly maxOctets = 10 * 1024 * 1024;
  readonly fichier = signal<File | null>(null);
  readonly ignorerDoublons = signal(true);
  readonly etape = signal<Etape>('choix');
  readonly enCours = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly resultat = signal<FisImportResponse | null>(null);
  readonly survol = signal(false);

  /** Lignes listées rejetées pour un motif « référentiel » ou « correspondance ». */
  readonly rejetsReferentiel = computed(
    () => this.resultat()?.erreurs_detail.filter((e) => MOTIF_REFERENTIEL.test(e)).length ?? 0,
  );

  /** Libellés FIS inconnus du Référentiel, sans doublon, dans l'ordre des rejets. */
  readonly libellesNonReconnus = computed<LibelleNonReconnu[]>(() => {
    const vus = new Map<string, LibelleNonReconnu>();
    for (const e of this.resultat()?.erreurs_detail ?? []) {
      const m = MOTIF_LIBELLE_INCONNU.exec(e);
      if (!m) continue;
      const categorie = CATEGORIES[m[1]];
      const cle = `${categorie}|${m[2].toLowerCase()}`;
      if (!vus.has(cle)) vus.set(cle, { categorie, nomCategorie: m[1], libelle: m[2] });
    }
    return [...vus.values()];
  });

  onFichier(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.choisir(input.files?.[0] ?? null);
    input.value = '';
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.survol.set(false);
    this.choisir(event.dataTransfer?.files?.[0] ?? null);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.survol.set(true);
  }

  private choisir(fichier: File | null): void {
    this.erreur.set(null);
    this.resultat.set(null);
    this.etape.set('choix');
    if (!fichier) return;
    if (!fichier.name.toLowerCase().endsWith('.xlsx')) {
      this.erreur.set('Fichier FIS attendu au format Excel (.xlsx).');
      return;
    }
    if (fichier.size > this.maxOctets) {
      this.erreur.set('Fichier trop volumineux (10 Mo maximum).');
      return;
    }
    this.fichier.set(fichier);
  }

  apercu(): void {
    this.envoyer(true);
  }

  importer(): void {
    this.envoyer(false);
  }

  recommencer(): void {
    this.fichier.set(null);
    this.resultat.set(null);
    this.erreur.set(null);
    this.etape.set('choix');
  }

  private envoyer(simulation: boolean): void {
    const fichier = this.fichier();
    if (!fichier || this.enCours()) return;
    this.enCours.set(true);
    this.erreur.set(null);
    this.service
      .importerFis(fichier, simulation, this.ignorerDoublons())
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          this.resultat.set(res);
          this.etape.set(simulation ? 'apercu' : 'termine');
          this.enCours.set(false);
        },
        error: (err: Error) => {
          this.erreur.set(err.message);
          this.enCours.set(false);
        },
      });
  }

  taille(octets: number): string {
    return octets < 1024 * 1024 ? `${Math.ceil(octets / 1024)} Ko` : `${(octets / 1024 / 1024).toFixed(1)} Mo`;
  }
}
