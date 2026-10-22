function resolveApiUrl(): string {
  const fallback = 'http://localhost:8000/api/v1';
  if (typeof window === 'undefined' || !window.location?.hostname) {
    return fallback;
  }
  return `http://${window.location.hostname}:8000/api/v1`;
}

export const environment = {
  production: false,
  apiUrl: resolveApiUrl(),
};
