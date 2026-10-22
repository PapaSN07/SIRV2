import { DecimalPipe } from '@angular/common';
import { Component, OnInit, inject, input, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AssistantChatResponse, RiskPrediction } from '../../../shared/models/assistant.models';
import { AssistantService } from '../services/assistant.service';

@Component({
  selector: 'sir-assistant-panel',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe],
  templateUrl: './assistant-panel.component.html',
  styleUrl: './assistant-panel.component.scss',
})
export class AssistantPanelComponent implements OnInit {
  private readonly assistant = inject(AssistantService);
  private readonly fb = inject(FormBuilder);

  readonly feederId = input<number | null>(null);
  readonly interruptionId = input<number | null>(null);
  readonly compact = input(false);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly risks = signal<RiskPrediction[]>([]);
  readonly reply = signal<AssistantChatResponse | null>(null);

  readonly form = this.fb.nonNullable.group({
    question: ['', [Validators.required, Validators.minLength(3)]],
  });

  ngOnInit(): void {
    this.reloadRisks();
  }

  reloadRisks(): void {
    this.loading.set(true);
    this.error.set(null);
    const feederId = this.feederId();
    this.assistant
      .listRisks({
        feeder_id: feederId ?? undefined,
        limit: this.compact() ? 5 : 15,
      })
      .subscribe({
        next: (res) => {
          this.risks.set(res.items);
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
  }

  ask(): void {
    if (this.form.invalid) return;
    this.loading.set(true);
    this.error.set(null);
    this.assistant
      .chat({
        question: this.form.controls.question.value,
        feeder_id: this.feederId(),
        interruption_id: this.interruptionId(),
      })
      .subscribe({
        next: (res) => {
          this.reply.set(res);
          if (res.predictions.length) {
            this.risks.set(res.predictions);
          }
          this.loading.set(false);
        },
        error: (err: Error) => {
          this.error.set(err.message);
          this.loading.set(false);
        },
      });
  }

  feedback(accepted: boolean): void {
    const conv = this.reply();
    if (!conv) return;
    this.assistant.feedback(conv.conversation_id, { accepted }).subscribe({
      error: (err: Error) => this.error.set(err.message),
    });
  }

  levelClass(level: string): string {
    return `risk-level risk-level--${level}`;
  }
}
