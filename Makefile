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

upgrade-senelec:
	cd sir-backend && set SIR_PROFILE=senelec&& alembic upgrade head

upgrade-docker:
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

seed-geo:
	docker compose exec api python -m scripts.run_seed_geo

seed-rbac:
	docker compose exec api python -m scripts.run_seed_rbac

seed-reseau:
	docker compose exec api python -m scripts.run_seed_reseau

seed-interruptions:
	docker compose exec api python -m scripts.run_seed_interruptions

seed-interruptions-transport:
	docker compose exec api python -m scripts.run_seed_interruptions_transport

seed-indicateurs:
	docker compose exec api python -m scripts.run_seed_indicateurs

seed-sig:
	docker compose exec api python -m scripts.run_seed_sig

seed-dev:
	docker compose exec api python -m scripts.run_seed_dev

# ── Profil bureau SENELEC (srv-bddomtech via Docker) ─────────────────────────

COMPOSE_SENELEC = docker compose --env-file .env.docker-senelec -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.senelec.yml

docker-senelec-env:
	powershell -ExecutionPolicy Bypass -File scripts/build-docker-senelec-env.ps1

up-senelec: docker-senelec-env
	$(COMPOSE_SENELEC) up -d redis api worker frontend

down-senelec:
	$(COMPOSE_SENELEC) down

logs-senelec:
	$(COMPOSE_SENELEC) logs -f api worker

# ── Utilitaires ───────────────────────────────────────────────────────────────

shell-api:
	docker compose exec api bash

shell-db:
	docker compose exec db /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$$DB_SA_PASSWORD" -C

ps:
	docker compose ps
