# Docker + PostgreSQL Setup

Status: **done and verified working** (see [Verification results](#verification-results)).

The JaGOOD stack (Postgres, internal FastAPI services, the public FastAPI gateway, and web
frontends) runs fully containerized via Docker Compose. The Route Planner's
BMKG API response cache moved from SQLite to PostgreSQL, and Postgres itself
runs as a container rather than a local file.

## Architecture

```
compose.yaml
├── postgres           postgres:16-alpine, host port 5432, volume-backed
├── route-planner      internal FastAPI + XGBoost service
├── ai-explain         internal FastAPI explanation service
├── platform-gateway   public FastAPI gateway, host port 8080
├── planner-web        Next.js dashboard, host port 3000
└── web                chatbot UI, host port 3001
```

- `route-planner` depends on `postgres` being healthy (`pg_isready` healthcheck)
  before it starts.
- `planner-web` is built with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080`
  baked in at build time (a `NEXT_PUBLIC_*` var is inlined into the client
  bundle, so it must point at whatever the *browser* can reach -- not the
  internal Docker network hostname).
- `route-planner`'s `DATABASE_URL` is overridden in `docker-compose.yml` to
  point at the `postgres` service hostname; `ORS_API_KEY` and
  `BMKG_BASE_URL` still come from `services/ai/route-planner/.env` via
  `env_file`.

## Files added/changed

| File | Change |
|---|---|
| `services/ai/route-planner/app/core/db.py` | SQLite -> PostgreSQL: `sqlalchemy.dialects.postgresql.insert` instead of `sqlite`, dropped SQLite-only `check_same_thread`, `payload` column changed to `Text` (was unbounded `String`), `fetched_at` now `DateTime(timezone=True)` |
| `services/ai/route-planner/app/core/config.py` | Default `database_url` now a `postgresql+psycopg2://...` URL |
| `services/ai/route-planner/requirements.txt` | Added `psycopg2-binary==2.9.10` |
| `services/ai/route-planner/.env`, `.env.example` | `DATABASE_URL` updated to Postgres |
| `services/ai/route-planner/Dockerfile` | New -- `python:3.12-slim`, installs `requirements.txt`, runs uvicorn |
| `services/ai/route-planner/.dockerignore` | New -- excludes `.venv/`, `.env`, `app_cache.db` |
| `frontend/Dockerfile` | New -- multi-stage (`deps` -> `builder` -> `runner`), uses `output: "standalone"` |
| `frontend/.dockerignore` | New |
| `frontend/next.config.ts` | Added `output: "standalone"` |
| `infrastructure/docker-compose.yml` | New -- the 3 services described above |
| `infrastructure/.env.example`, `.env` | New -- `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` |
| `Makefile` | Added `docker-up`, `docker-up-db`, `docker-down`, `docker-build`, `docker-logs`, `docker-clean` |

## Usage

```
cd infrastructure
cp .env.example .env      # adjust Postgres credentials if needed
docker compose up --build -d
```

Or from the repo root: `make docker-up`.

- Frontend: http://localhost:3000
- Platform gateway + Swagger UI: http://localhost:8080/docs
- Postgres: `localhost:5432` (credentials from `infrastructure/.env`)

Useful commands:

```
docker compose ps                # container status
docker compose logs -f           # follow logs from all 3 services
docker compose down              # stop + remove containers
docker compose down --volumes    # also wipe the Postgres data volume
```

### Local backend dev against a Dockerized Postgres

`make docker-up-db` starts only the `postgres` container on `localhost:5432`,
so the backend can be run directly (`make run-backend`) without
containerizing it, while still using Postgres instead of SQLite.

## Verification results

Verified on 2026-08-23 with the platform gateway architecture:

```bash
docker compose config
docker compose up -d --build platform-gateway
curl http://localhost:8080/health
curl http://localhost:8080/ready
curl http://localhost:8080/commodities/provenance
curl http://localhost:8080/openapi.json
```

The gateway returned HTTP 200 for health/readiness, exposed the combined OpenAPI title
`JaGOOD Platform API Gateway`, forwarded commodity provenance, and successfully processed an
end-to-end `POST /final-recommendation` request through the internal Route Planner. Gateway unit
tests also cover Route Planner query forwarding, AI Explain SSE forwarding, Final Recommendation
orchestration, readiness, and upstream-error mapping.

## Known gotchas

- **The `xgboost` Linux wheel pulls in `nvidia-nccl-cu13` (~216MB)** as a
  transitive dependency even for CPU-only use (the Windows wheel doesn't
  have this dependency, so it's easy to miss locally). This can cause `pip
  install` to time out during `docker build` on a slow connection --
  `Dockerfile` sets `--timeout 120 --retries 10` on the pip install to
  ride it out. If the build still times out, just re-run
  `docker compose up --build -d`; Docker's layer cache means completed
  layers aren't re-downloaded.
- **Docker Desktop/Rancher Desktop on Windows requires WSL2 with at least
  one distro installed.** If `docker ps` fails with `failed to connect to
  the docker API at npipe:////./pipe/docker_engine`, check `wsl -l -v` --
  if it reports no installed distributions, run `wsl --install`, then
  **restart the Docker/Rancher Desktop application** (it needs to detect
  WSL2 becoming available; simply installing WSL while the app is already
  running isn't enough, it doesn't retry on its own).
