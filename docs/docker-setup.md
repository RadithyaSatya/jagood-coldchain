# Docker + PostgreSQL Setup

Status: **done and verified working** (see [Verification results](#verification-results)).

The Smart Route Planner stack (Postgres, the FastAPI backend, the Next.js
frontend) now runs fully containerized via Docker Compose. The backend's
BMKG API response cache moved from SQLite to PostgreSQL, and Postgres itself
runs as a container rather than a local file.

## Architecture

```
infrastructure/docker-compose.yml
├── postgres          postgres:16-alpine, port 5432, volume-backed
├── route-planner      services/ai/route-planner (FastAPI + XGBoost), port 8000
└── frontend           frontend (Next.js, standalone build), port 3000
```

- `route-planner` depends on `postgres` being healthy (`pg_isready` healthcheck)
  before it starts.
- `frontend` is built with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
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
- Backend + Swagger UI: http://localhost:8000/docs
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

Run on 2026-08-05 after the stack came up clean:

```
$ docker compose ps
NAME                             STATUS                    PORTS
infrastructure-postgres-1        Up (healthy)              0.0.0.0:5432->5432/tcp
infrastructure-route-planner-1   Up                        0.0.0.0:8000->8000/tcp
infrastructure-frontend-1        Up                        0.0.0.0:3000->3000/tcp

$ curl http://localhost:8000/health
{"status":"ok"}

$ curl -o /dev/null -w "%{http_code}" http://localhost:8000/docs
200

$ curl -X POST http://localhost:8000/predict-route -H "Content-Type: application/json" -d '{...Jakarta->Surabaya, Salmon Segar...}'
{"shipment_id":"shp-4c247e14b1fd","recommended_route":{"route_id":"darat-1","transport_mode":"darat",
"distance_km":770.3,"estimated_duration_hours":10.14,"risk_level":"Low", ...},"alternative_routes":[...]}

$ curl -o /dev/null -w "%{http_code}" http://localhost:3000/
200

$ docker compose exec postgres psql -U route_planner -d route_planner -c "\dt"
 Schema |    Name    | Type  |     Owner
--------+------------+-------+---------------
 public | bmkg_cache | table | route_planner

$ docker compose exec postgres psql -U route_planner -d route_planner \
    -c "SELECT cache_key, fetched_at FROM bmkg_cache LIMIT 5;"
                     cache_key                      |          fetched_at
----------------------------------------------------+-------------------------------
 geojson:wilayah_perairan                           | 2026-08-05 17:01:08.978593+00
 perairan:I.07_Perairan Gresik - Surabaya.json      | 2026-08-05 17:01:09.143473+00
 index:perairan_list                                | 2026-08-05 17:01:09.240786+00
 ...
```

Confirms: Postgres container healthy, `route-planner` connects to it and
creates/uses the `bmkg_cache` table (real BMKG API responses cached, not
SQLite), `predict-route` returns a correct end-to-end response, and the
frontend serves successfully -- all through Docker only.

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
