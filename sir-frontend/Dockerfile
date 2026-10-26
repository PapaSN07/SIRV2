FROM node:20-alpine AS base

WORKDIR /app

# ── Dépendances ─────────────────────────────────────────────────────────────
FROM base AS deps

COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

# ── Développement (ng serve via volume) ─────────────────────────────────────
FROM deps AS development

ENV NODE_ENV=development

COPY . .

CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--port", "4200"]

# ── Build production ─────────────────────────────────────────────────────────
FROM deps AS builder

ENV NODE_ENV=production

COPY . .
RUN npx ng build --configuration production --output-path /dist

# ── Serveur Nginx production ─────────────────────────────────────────────────
FROM nginx:1.27-alpine AS production

COPY --from=builder /dist/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
    CMD wget -qO- http://localhost/health || exit 1

EXPOSE 80
