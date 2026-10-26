import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { TronconSig, TronconSigChaine } from '../../../shared/models/sig.models';
import { SigService } from '../services/sig.service';

@Component({
  selector: 'sir-sig-troncon-picker',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './sig-troncon-picker.component.html',
  styleUrl: './sig-troncon-picker.component.scss',
})
export class SigTronconPickerComponent {
  private readonly sig = inject(SigService);

  readonly open = input(false);
  readonly feederId = input<number | null>(null);

  readonly closed = output<void>();
  readonly selected = output<TronconSigChaine>();

  readonly items = signal<TronconSig[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly search = signal('');
  readonly preview = signal<TronconSigChaine | null>(null);
  readonly previewLoading = signal(false);
  readonly activeId = signal<number | null>(null);

  constructor() {
    // load() met à jour des signaux (chargement, liste) : écriture autorisée dans l'effet
    effect(
      () => {
        if (this.open()) {
          this.load();
        }
      },
      { allowSignalWrites: true },
    );
  }

  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('sig-modal')) {
      this.close();
    }
  }

  close(): void {
    this.preview.set(null);
    this.activeId.set(null);
    this.closed.emit();
  }

  load(): void {
    const feederId = this.feederId();
    if (!feederId) {
      this.error.set("Feeder non renseigné sur l'interruption.");
      this.items.set([]);
      return;
    }
    this.loading.set(true);
    this.error.set(null);
    this.sig
      .listTroncons({
        feeder_id: feederId,
        page_size: 100,
        search: this.search() || undefined,
      })
      .subscribe({
        next: (res) => {
          this.items.set(res.items);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
  }

  onSearchChange(value: string): void {
    this.search.set(value);
    this.load();
  }

  pick(troncon: TronconSig): void {
    this.activeId.set(troncon.id);
    this.previewLoading.set(true);
    this.sig.getChaineAval(troncon.id, 3).subscribe({
      next: (chain) => {
        this.preview.set(chain);
        this.previewLoading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.previewLoading.set(false);
      },
    });
  }

  confirm(): void {
    const chain = this.preview();
    if (!chain) return;
    this.selected.emit(chain);
    this.close();
  }

  segmentLabel(t: TronconSig): string {
    const amont = t.nom_noeud_amont || t.code_noeud_amont || '?';
    const aval = t.nom_noeud_aval || t.code_noeud_aval || '?';
    return `${amont} → ${aval}`;
  }
}
