import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'sir-paginator',
  standalone: true,
  templateUrl: './paginator.component.html',
  styleUrl: './paginator.component.scss',
})
export class PaginatorComponent {
  @Input({ required: true }) total!: number;
  @Input({ required: true }) page!: number;
  @Input({ required: true }) pageSize!: number;
  @Input() pageSizeOptions: number[] = [10, 20, 50];

  @Output() readonly pageChange = new EventEmitter<number>();
  @Output() readonly pageSizeChange = new EventEmitter<number>();

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.total / this.pageSize));
  }

  get rangeStart(): number {
    return this.total === 0 ? 0 : (this.page - 1) * this.pageSize + 1;
  }

  get rangeEnd(): number {
    return Math.min(this.page * this.pageSize, this.total);
  }

  visiblePages(): number[] {
    const total = this.totalPages;
    const current = this.page;
    if (total <= 7) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }
    const pages: number[] = [1];
    if (current > 3) pages.push(-1);
    for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p += 1) {
      pages.push(p);
    }
    if (current < total - 2) pages.push(-1);
    pages.push(total);
    return pages;
  }

  goToPage(nextPage: number): void {
    const page = Math.min(Math.max(1, nextPage), this.totalPages);
    if (page !== this.page) {
      this.pageChange.emit(page);
    }
  }

  onPageSizeSelect(value: string): void {
    const size = Number(value);
    if (size !== this.pageSize) {
      this.pageSizeChange.emit(size);
    }
  }
}
