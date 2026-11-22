#!/usr/bin/env bash
# Golden-path browser test against the running stack (make up first).
# Creates a throwaway organisation and admin, then runs Playwright.
set -euo pipefail
cd "$(dirname "$0")/.."
export E2E_EMAIL="e2e-$(date +%s)-$RANDOM@example.com"
export E2E_PASSWORD="e2e-$(openssl rand -hex 12)"
docker compose -f infra/docker-compose.yml exec -T -e ARCHMIND_ADMIN_PASSWORD="$E2E_PASSWORD" api \
  uv run --no-dev python -m archmind.cli create-admin "E2E org" "$E2E_EMAIL" "E2E Admin"
cd apps/web
npx playwright install chromium >/dev/null
npx playwright test "$@"
