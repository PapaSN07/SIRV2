export interface ApiResponse<T> {
  status: 'success' | 'error';
  data: T | null;
  error: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaginationParams {
  page?: number;
  size?: number;
}
