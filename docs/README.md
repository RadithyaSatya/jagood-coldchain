# docs

Project-wide documentation.

Service-specific docs (PRDs, API references) live next to their service --
e.g. the Smart Route Planner's PRD is at
[`services/ai/route-planner/smart-router-prd.md`](../services/ai/route-planner/smart-router-prd.md).
Its API is self-documenting via FastAPI's Swagger UI -- see that service's
README for the URL.

- [Docker + PostgreSQL setup](docker-setup.md) -- containerized stack (Postgres, backend, frontend), verification results, known gotchas.
- [`dev-bayu` branch documentation](dev-bayu.md) ([PDF](dev-bayu.pdf)) -- full walkthrough of the Smart Route Planner: architecture, the XGBoost risk model and its measured metrics, risk-first route ranking, SHAP explainability, cargo-temperature simulation, API reference, setup guide, and known limitations.
- [`Hackathon demo runbook`](DEMO_RUNBOOK.md) -- preflight checks, a 5–8 minute judge flow, offline fallback path, troubleshooting, and safe claim boundaries.
- [`Capability and claim matrix`](CAPABILITY_MATRIX.md) -- implemented, limited, and missing capabilities plus the current data classifications.
