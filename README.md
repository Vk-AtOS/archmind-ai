# ArchMind AI
Plot and brief to a rule-compliant house design with a build cost. Private repository.

Specs and decisions: Confluence space ARCHMIND (start with "Strategy v2: Analyze, Suggest, Build (ADOPTED)" and "Execution Roadmap (v0)"). Work: Jira project ARCH, `labels = v0`.

## Layout
- `apps/api` FastAPI (Python 3.12, uv)
- `apps/web` Next.js (Node 20)
- `infra/docker-compose.yml` local stack: postgres, redis, api, web
- `docs/adr` decision records (canonical copy in Confluence)

## Commands
| Command | What it does |
|---|---|
| `make setup` | install API and web dependencies |
| `make up` / `make down` | start / stop the local stack (Docker Desktop must be running) |
| `make smoke` | check API health and that the web page reaches the API |
| `make lint` | ruff, mypy, eslint, tsc |
| `make test` | API tests |

Web: http://localhost:3000 · API: http://localhost:8000/api/v1/health
