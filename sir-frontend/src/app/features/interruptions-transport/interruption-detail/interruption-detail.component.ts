import { Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { AuthService } from '../../../core/auth/auth.service';
import { HasRoleDirective } from '../../../core/auth/has-role.directive';
import { InterruptionTransportDetail } from '../../../shared/models/interruption-transport.models';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { StatusChipComponent } from '../../../shared/ui/status-chip/status-chip.component';
import { InterruptionsNavComponent } from '../../../shared/ui/interruptions-nav/interruptions-nav.component';
import { InterruptionTransportService } from '../services/interruption-transport.service';

@Component({
  selector: 'sir-interruption-transport-detail',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    DatePipe,
    HasRoleDirective,
    PageHeaderComponent,
    StatusChipComponent,
    InterruptionsNavComponent,
  ],
  templateUrl: './interruption-detail.component.html',
  styleUrl: './interruption-detail.component.scss',
})
export class InterruptionTransportDetailComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly service = inject(InterruptionTransportService);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);

  readonly timelineSteps = [
    { key: 'en_cours', label: 'En cours' },
    { key: 'cloture', label: 'Clôturée' },
    { key: 'valide', label: 'Validée' },
  ] as const;

  readonly item = signal<InterruptionTransportDetail | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly actionError = signal<string | null>(null);

  readonly clotureForm = this.fb.nonNullable.group({
    date_remise: ['', Validators.required],
  });

  ngOnInit(): void {
    if (!this.auth.currentUser()) {
      this.auth.fetchMe().subscribe();
    }
    const id = Number(this.route.snapshot.paramMap.get('id'));
    this.load(id);
  }

  canEdit(it: InterruptionTransportDetail): boolean {
    return it.statut === 'en_cours' && this.auth.hasRole('DISPATCHER', 'ADMIN_DISPATCHING');
  }

  typeLabel(type: string): string {
    return type === 'omvg' ? 'OMVG' : 'Transport HTB';
  }

  stepDone(stepKey: string, current: string): boolean {
    const order = ['en_cours', 'cloture', 'valide', 'archive'];
    return order.indexOf(current) > order.indexOf(stepKey);
  }

  cloturer(): void {
    const it = this.item();
    if (!it || this.clotureForm.invalid) return;
    const dateIso = new Date(this.clotureForm.value.date_remise!).toISOString();
    this.actionError.set(null);
    this.service.cloturer(it.id, { date_remise: dateIso }).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  valider(): void {
    const it = this.item();
    if (!it) return;
    this.actionError.set(null);
    this.service.valider(it.id).subscribe({
      next: () => this.load(it.id),
      error: (err: Error) => this.actionError.set(err.message),
    });
  }

  private load(id: number): void {
    this.loading.set(true);
    this.error.set(null);
    this.service.get(id).subscribe({
      next: (detail) => {
        this.item.set(detail);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }
}
