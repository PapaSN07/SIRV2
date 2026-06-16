import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatOptionModule } from '@angular/material/core';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatToolbarModule } from '@angular/material/toolbar';
import { RouterLink } from '@angular/router';
import { GeoService } from '../services/geo.service';
import { Agence, Delegation, Region, Service } from '../../../shared/models/geo.models';

@Component({
  selector: 'sir-geo-cascade',
  standalone: true,
  imports: [
    RouterLink,
    ReactiveFormsModule,
    MatToolbarModule,
    MatButtonModule,
    MatFormFieldModule,
    MatSelectModule,
    MatOptionModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <mat-toolbar color="primary">
      <a mat-button routerLink="/">← Accueil</a>
      <span>Hiérarchie géographique</span>
    </mat-toolbar>

    <main class="content">
      @if (loading()) {
        <mat-spinner diameter="40" />
      } @else if (error()) {
        <p class="error">{{ error() }}</p>
      } @else {
        <form [formGroup]="form" class="cascade">
          <mat-form-field appearance="outline">
            <mat-label>Région</mat-label>
            <mat-select formControlName="regionId">
              @for (r of regions(); track r.id) {
                <mat-option [value]="r.id">{{ r.code }} — {{ r.libelle }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Délégation</mat-label>
            <mat-select formControlName="delegationId" [disabled]="!delegations().length">
              @for (d of delegations(); track d.id) {
                <mat-option [value]="d.id">{{ d.code }} — {{ d.libelle }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Agence</mat-label>
            <mat-select formControlName="agenceId" [disabled]="!agences().length">
              @for (a of agences(); track a.id) {
                <mat-option [value]="a.id">{{ a.code }} — {{ a.libelle }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Service</mat-label>
            <mat-select formControlName="serviceId" [disabled]="!services().length">
              @for (s of services(); track s.id) {
                <mat-option [value]="s.id">{{ s.code }} — {{ s.libelle }}</mat-option>
              }
            </mat-select>
          </mat-form-field>
        </form>

        @if (selectedService(); as svc) {
          <section class="summary">
            <h3>Service sélectionné</h3>
            <p><strong>Code :</strong> {{ svc.code }}</p>
            <p><strong>Libellé :</strong> {{ svc.libelle }}</p>
            <p><strong>ID :</strong> {{ svc.id }}</p>
          </section>
        }
      }
    </main>
  `,
  styles: [
    `
      .content {
        padding: 24px;
      }
      .cascade {
        display: grid;
        gap: 16px;
        max-width: 480px;
      }
      .summary {
        margin-top: 24px;
        padding: 16px;
        background: #fff;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
      }
      .error {
        color: #dc2626;
      }
    `,
  ],
})
export class GeoCascadeComponent implements OnInit {
  private readonly geo = inject(GeoService);

  readonly form = new FormGroup({
    regionId: new FormControl<number | null>(null),
    delegationId: new FormControl<number | null>(null),
    agenceId: new FormControl<number | null>(null),
    serviceId: new FormControl<number | null>(null),
  });

  readonly regions = signal<Region[]>([]);
  readonly delegations = signal<Delegation[]>([]);
  readonly agences = signal<Agence[]>([]);
  readonly services = signal<Service[]>([]);
  readonly selectedService = signal<Service | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.geo.getRegions().subscribe({
      next: (regions) => {
        this.regions.set(regions);
        this.loading.set(false);
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });

    this.form.controls.regionId.valueChanges.subscribe((regionId) => {
      this.resetBelow('region');
      if (!regionId) return;
      this.geo.getDelegations(regionId).subscribe({
        next: (items) => this.delegations.set(items),
        error: (err: Error) => this.error.set(err.message),
      });
    });

    this.form.controls.delegationId.valueChanges.subscribe((delegationId) => {
      this.resetBelow('delegation');
      if (!delegationId) return;
      this.geo.getAgences(delegationId).subscribe({
        next: (items) => this.agences.set(items),
        error: (err: Error) => this.error.set(err.message),
      });
    });

    this.form.controls.agenceId.valueChanges.subscribe((agenceId) => {
      this.resetBelow('agence');
      if (!agenceId) return;
      this.geo.getServices(agenceId).subscribe({
        next: (items) => this.services.set(items),
        error: (err: Error) => this.error.set(err.message),
      });
    });

    this.form.controls.serviceId.valueChanges.subscribe((serviceId) => {
      const svc = this.services().find((s) => s.id === serviceId) ?? null;
      this.selectedService.set(svc);
    });
  }

  private resetBelow(level: 'region' | 'delegation' | 'agence'): void {
    if (level === 'region') {
      this.form.patchValue(
        { delegationId: null, agenceId: null, serviceId: null },
        { emitEvent: false },
      );
      this.delegations.set([]);
      this.agences.set([]);
      this.services.set([]);
    } else if (level === 'delegation') {
      this.form.patchValue({ agenceId: null, serviceId: null }, { emitEvent: false });
      this.agences.set([]);
      this.services.set([]);
    } else {
      this.form.patchValue({ serviceId: null }, { emitEvent: false });
      this.services.set([]);
    }
    this.selectedService.set(null);
  }
}
