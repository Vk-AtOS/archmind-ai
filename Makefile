COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: setup up down logs test lint smoke admin e2e

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
	curl -fsS --retry 5 --retry-all-errors --retry-delay 1 localhost:8000/api/v1/health
	curl -fsS --retry 5 --retry-all-errors --retry-delay 1 localhost:3000 | grep -q 'API ok'

admin:
	$(COMPOSE) exec api uv run --no-dev python -m archmind.cli create-admin "$(ORG)" "$(EMAIL)" "$(NAME)"

e2e:
	./scripts/e2e.sh
