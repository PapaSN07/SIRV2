import { Directive, Input, TemplateRef, ViewContainerRef, inject, OnChanges } from '@angular/core';
import { AuthService } from './auth.service';

@Directive({
  selector: '[sirHasRole]',
  standalone: true,
})
export class HasRoleDirective implements OnChanges {
  private readonly templateRef = inject(TemplateRef<unknown>);
  private readonly viewContainer = inject(ViewContainerRef);
  private readonly auth = inject(AuthService);

  @Input({ required: true }) sirHasRole!: string[];

  ngOnChanges(): void {
    this.viewContainer.clear();
    if (this.auth.hasRole(...this.sirHasRole)) {
      this.viewContainer.createEmbeddedView(this.templateRef);
    }
  }
}
