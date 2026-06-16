import { Component, Input } from '@angular/core';
import { StatutInterruption } from '../../models/interruption.models';
import { statutLabel } from '../../utils/statut.utils';

@Component({
  selector: 'sir-status-chip',
  standalone: true,
  template: `
    <span class="status-chip" [class]="'status-chip--' + statut">
      {{ label }}
    </span>
  `,
  styleUrl: './status-chip.component.scss',
})
export class StatusChipComponent {
  @Input({ required: true }) statut!: StatutInterruption;

  get label(): string {
    return statutLabel(this.statut);
  }
}
