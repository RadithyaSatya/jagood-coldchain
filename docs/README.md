# docs

Project-wide documentation.

Service-specific docs (PRDs, API references) live next to their service --
e.g. the Smart Route Planner's PRD is at
[`services/ai/route-planner/smart-router-prd.md`](../services/ai/route-planner/smart-router-prd.md).
Its API is self-documenting via FastAPI's Swagger UI -- see that service's
README for the URL.

- [Docker + PostgreSQL setup](docker-setup.md) -- containerized stack (Postgres, backend, frontend), verification results, known gotchas.
