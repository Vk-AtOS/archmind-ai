COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: setup up down logs test lint smoke

setup:
	cd apps/api && uv sync
	cd apps/web && npm ci --no-audit --no-fund

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

lint:
	cd apps/api && uv run ruff check . && uv run ruff format --check . && uv run mypy
	cd apps/web && npm run lint && npm run typecheck

test:
	cd apps/api && uv run pytest -q

smoke:
	curl -fsS localhost:8000/api/v1/health && curl -fsS localhost:3000 | grep -q 'API ok'
