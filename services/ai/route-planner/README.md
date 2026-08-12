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

## Route ranking (`ranking_preference`)

`POST /predict-route` accepts `ranking_preference`:

- **`"risiko"` (default)** -- ranks by the model's predicted cargo-damage risk
  first, using travel time only to break ties between equally-risky routes.
  This is PRD FR-5's risk-first ordering and the product's actual
  differentiator: the recommended route is the *safest* one, which may well be
  slower than the fastest available.
- **`"kecepatan"`** -- ranks purely by travel time, i.e. what a general-purpose
  route planner does. Risk is still predicted, explained and displayed; it just
  doesn't affect ordering. Useful for showing the two side by side.

An unrecognized value falls back to `"risiko"` rather than to speed, since
silently ranking a cold-chain shipment by speed is the more dangerous failure.

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
- **`port_ambient_temp_c`** (real BMKG air temperature at the hotter
  embark/disembark port) is a proxy for reefer/equipment stress risk during
  port dwell time -- it is *not* the cargo's actual temperature, and there is
  no data source for real refrigeration-unit reliability. Its contribution to
  the model is intentionally modest (feature importance ~0.001-0.0014) for
  this reason; land-only routes get a neutral default (30.0C) that adds no
  risk.
- The public OpenRouteService instance has occasional road-graph data gaps
  in Indonesia (observed: a 13km Jakarta hop resolving to a 1500km+ detour).
  Route legs are sanity-checked against straight-line distance and replaced
  with a distance-based estimate when implausible; affected candidates are
  marked `"data_quality": "estimated"` in the API response.
- **`risk_explanation_summary`/`risk_explanation_factors`** (FR-8, per-route
  explainability) are generated from SHAP values computed in the model's raw
  margin (pre-softmax) space, then combined with the same 0.5/1.0 weights as
  `risk_probability`. This is a practical approximation for ranking *which*
  features drove a multi-class tree model's prediction and in which
  direction -- margin-space contributions don't sum linearly into a
  probability-space metric the way they do in margin space itself, so treat
  it as a qualitative explanation, not an exact probability decomposition.
- BMKG and OpenRouteService responses are cached (Postgres, a few hours TTL)
  to stay within free-tier rate limits during a live demo.
- **`cold_chain_equipment: "pasif"`** (no active reefer) simulates cargo
  temperature against real Open-Meteo ambient air temperature along the
  route (exponential heat-transfer model, Q10=2.5 shelf-life acceleration
  above the commodity's ideal temp). This is the physically-appropriate case
  for the Q10 principle -- unlike `port_ambient_temp_c` above, cargo
  temperature genuinely tracks ambient conditions here since there's no
  active cooling. Default remains `"reefer"` (today's behavior, unaffected,
  zero added latency/external-API risk). Assumptions worth flagging: initial
  cargo temp is assumed at the commodity's ideal on departure (proper
  pre-cooling), insulation quality (`baik`/`sedang`/`buruk`) maps to a fixed
  heat-transfer constant rather than a measured value, and no ice-pack/
  phase-change reserve is modeled (a real passive cooler with ice packs
  would resist warming longer than this model predicts).
