.PHONY: up down logs build migrate upgrade downgrade test setup

# ── Environnement ─────────────────────────────────────────────────────────────

setup:
	cp -n .env.example .env || true
	@echo "→ Édite .env avec tes valeurs avant de lancer 'make up'"

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

logs-worker:
	docker compose logs -f worker

restart-api:
	docker compose restart api

# ── Base de données ───────────────────────────────────────────────────────────

migrate:
	docker compose exec api alembic revision --autogenerate -m "$(msg)"

upgrade:
	docker compose exec api alembic upgrade head

downgrade:
	docker compose exec api alembic downgrade -1

# ── Tests ─────────────────────────────────────────────────────────────────────

test:
	docker compose exec api pytest tests/ -v

test-unit:
	docker compose exec api pytest tests/unit/ -v

test-integration:
	docker compose exec api pytest tests/integration/ -v

# ── Utilitaires ───────────────────────────────────────────────────────────────

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec db /opt/mssql-tools/bin/sqlcmd -S localhost -U sa -P "$$DB_SA_PASSWORD"

ps:
	docker compose ps
