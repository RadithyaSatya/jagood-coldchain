# Smart Route Planner

AI-powered route recommendation for cold chain logistics. See
[`smart-router-prd.md`](smart-router-prd.md) for the full spec.

## Setup

Needs a reachable Postgres (used to cache BMKG API responses). Easiest via
Docker -- see [`../../../infrastructure`](../../../infrastructure) to run
everything (Postgres + this backend + the frontend), or `make docker-up-db`
from the repo root to start just Postgres and run this service locally:

```
cd services/ai/route-planner
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # .venv/bin/pip on macOS/Linux
cp .env.example .env                                # fill in ORS_API_KEY; DATABASE_URL defaults to localhost:5432

python -m training.synthetic_corridors
python -m training.generate_synthetic_data
python -m training.train_model
python -m training.evaluate_model

python -m uvicorn app.main:app --reload
```

The frontend at [`../../../frontend`](../../../frontend) calls this API at
`http://localhost:8000` by default (see its `.env.local`).

## API docs (Swagger)

FastAPI serves interactive Swagger UI automatically once the server is
running:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Raw OpenAPI schema: http://localhost:8000/openapi.json

## Scenario validation

```
python -m scripts.validate_scenarios
```

Runs several commodity/route/season combinations plus one forced
extreme-weather case against the pipeline directly, validating FR-6
(extreme conditions demote a candidate + set `trigger_reason` rather than
hard-blocking it).

## Known limitations for judges/reviewers

- **Historical delay/damage data is synthetic**, generated from a rule-based
  model with injected noise (`training/generate_synthetic_data.py`) rather
  than real shipment records. It has not been validated against real-world
  outcomes. The held-out test recall on the "High" risk class is 0.996
  (target was >=0.80), which reflects how learnable the synthetic label
  function is, not real-world classifier performance.
- **`searoute-py`** produces sea routes for distance/duration estimation and
  visualization; it is not a maritime navigation tool.
- **`port_status_flag`** is a proxy derived from BMKG wave-category
  forecasts, not an official real-time port operational status (no public
  Inaportnet API exists for this).
- The public OpenRouteService instance has occasional road-graph data gaps
  in Indonesia (observed: a 13km Jakarta hop resolving to a 1500km+ detour).
  Route legs are sanity-checked against straight-line distance and replaced
  with a distance-based estimate when implausible; affected candidates are
  marked `"data_quality": "estimated"` in the API response.
- BMKG and OpenRouteService responses are cached (Postgres, a few hours TTL)
  to stay within free-tier rate limits during a live demo.
