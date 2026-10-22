import { Component, OnInit, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { DatamartSummary, RiskListResponse } from '../../../shared/models/assistant.models';
import { AnalyticsNavComponent } from '../../../shared/ui/analytics-nav/analytics-nav.component';
import { PageHeaderComponent } from '../../../shared/ui/page-header/page-header.component';
import { AssistantPanelComponent } from '../assistant-panel/assistant-panel.component';
import { AssistantService } from '../services/assistant.service';

@Component({
  selector: 'sir-assistant-hub',
  standalone: true,
  imports: [PageHeaderComponent, AnalyticsNavComponent, AssistantPanelComponent],
  templateUrl: './assistant-hub.component.html',
  styleUrl: './assistant-hub.component.scss',
})
export class AssistantHubComponent implements OnInit {
  private readonly assistant = inject(AssistantService);
  private readonly auth = inject(AuthService);

  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly risks = signal<RiskListResponse | null>(null);
  readonly datamart = signal<DatamartSummary | null>(null);
  readonly scoringMsg = signal<string | null>(null);

  canAdmin(): boolean {
    return this.auth.hasRole('ADMIN_SCR', 'ADMIN_SAQS', 'SUPERADMIN');
  }

  ngOnInit(): void {
    this.reload();
  }

  reload(): void {
    this.loading.set(true);
    this.error.set(null);
    this.assistant.listRisks({ limit: 20 }).subscribe({
      next: (risks) => {
        this.risks.set(risks);
        this.assistant.getDatamart().subscribe({
          next: (dm) => {
            this.datamart.set(dm);
            this.loading.set(false);
          },
          error: (err: Error) => {
            this.error.set(err.message);
            this.loading.set(false);
          },
        });
      },
      error: (err: Error) => {
        this.error.set(err.message);
        this.loading.set(false);
      },
    });
  }

  runScoring(): void {
    if (!this.canAdmin()) return;
    this.scoringMsg.set(null);
    this.assistant.runScoring(90).subscribe({
      next: (res) => {
        this.scoringMsg.set(
          `Scoring ${res.model_version} : ${res.feeders_scored} feeder(s) (horizon ${res.horizon_days} j)`,
        );
        this.reload();
      },
      error: (err: Error) => this.scoringMsg.set(err.message),
    });
  }
}
