# infrastructure

`docker-compose.yml` runs the whole stack: Postgres, the route-planner
backend, and the frontend.

## Usage

```
cd infrastructure
cp .env.example .env      # adjust Postgres credentials if needed
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend + Swagger UI: http://localhost:8000/docs
- Postgres: localhost:5432 (credentials from `.env`)

Or from the repo root: `make docker-up` / `make docker-down` / `make docker-logs`.

The backend container reads `services/ai/route-planner/.env` for
`ORS_API_KEY` (fill that in first -- see that service's README), with
`DATABASE_URL` overridden here to point at the `postgres` container instead
of localhost.

### Running Postgres only (for local, non-Docker backend development)

```
make docker-up-db
```

Starts just the `postgres` container on `localhost:5432` so you can run the
backend directly with `make run-backend` while developing, without
containerizing it.

See [`../docs/docker-setup.md`](../docs/docker-setup.md) for the full
architecture, verification results, and known gotchas (e.g. the WSL2
requirement for Docker/Rancher Desktop on Windows).

Not implemented yet: CI/CD pipelines, Kubernetes manifests, Terraform.
