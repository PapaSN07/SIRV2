import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FisImportResponse } from '../../../shared/models/interruption.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { InterruptionDistributionService } from '../services/interruption-distribution.service';

type Etape = 'choix' | 'apercu' | 'termine';

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

  readonly maxOctets = 10 * 1024 * 1024;
  readonly fichier = signal<File | null>(null);
  readonly ignorerDoublons = signal(true);
  readonly etape = signal<Etape>('choix');
  readonly enCours = signal(false);
  readonly erreur = signal<string | null>(null);
  readonly resultat = signal<FisImportResponse | null>(null);
  readonly survol = signal(false);

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
    this.service.importerFis(fichier, simulation, this.ignorerDoublons()).subscribe({
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
