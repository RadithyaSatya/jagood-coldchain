# Jagood ColdChain

Jagood ColdChain is a hackathon decision-support prototype for planning cold-chain food delivery. It combines an XGBoost risk classifier, deterministic route/scenario logic, SHAP-based factor ranking, and an optional LLM explanation layer.

Food products such as fresh produce, seafood, dairy, meat, and frozen goods require stable temperatures throughout their journey. Route changes, delays, or transportation disruptions can reduce food quality, shorten shelf life, and cause significant losses. Jagood ColdChain helps users identify these risks earlier and make better-informed decisions.

## Key Features

### Smart Route Planner — implemented with MVP limitations

Ranks generated route candidates using travel time and a model-estimated quality-risk category. The dashboard compares risk score, duration, distance, routing fallback, and environmental-data quality side by side. The model was trained on synthetic labels, so its output demonstrates the pipeline rather than validated real-world spoilage probability.

### Scenario Simulator — implemented

Re-runs the same analytical pipeline for changes to delay, transport mode, cooling equipment, or insulation. It is a deterministic counterfactual comparison, not Monte Carlo simulation or a separately trained scenario model.

### Transportation Monitoring — not implemented

The repository does not ingest live GPS, IoT sensors, or stored shipment telemetry. Monitoring remains future work.

### AI Explain — implemented with fallback

Explains structured planner/scenario results using an OpenAI-compatible local LLM. It does not calculate risk or routes. When the LLM is unavailable, the service returns a deterministic summary of the supplied analytical facts.

### Scoped Cold-Chain Chatbot

Supports multi-turn questions about shipment status, risk, routes, recommendations, and
simulation results. A rule-based intent allowlist rejects unrelated topics before they reach
the language model, while shipment calculations remain owned by the application.

The API accepts up to 10 previous messages and an optional structured shipment context:

```bash
curl http://localhost:8001/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "language": "id",
    "message": "Kenapa risiko pengiriman ini sedang?",
    "shipment_context": {
      "shipment_id": "SHP-123",
      "source": "scenario_simulator",
      "product": "Salmon Segar",
      "facts": {"risk_delta": "48.92 poin persentase"},
      "risk_level": "medium"
    }
  }'
```

Use `POST /v1/chat/stream` for an SSE response. Clients should send the returned user and
assistant messages back through `history`; the service deliberately does not maintain server-side
session state.

Jagood product questions use a lightweight Markdown knowledge base from
`services/ai/ai-explain/knowledge/`. Relevant sections are selected locally and
returned through the chat response's `sources` field. Add or update `.md` files in that directory
to maintain the chatbot's knowledge; no embedding model or vector database is required.

## Goals

These are intended product outcomes, not benefits already proven by the current MVP:

- Reduce the risk of food spoilage during delivery.
- Support more effective distribution planning.
- Provide early warnings for potential disruptions.
- Enable decision-making based on clear and relevant information.
- Improve transparency across the cold-chain transportation process.

## Project Status

Jagood ColdChain is a hackathon MVP, not a production food-safety, navigation, or shipment-monitoring system. See the [current capability and claim matrix](docs/CAPABILITY_MATRIX.md) before evaluating feature or data claims.

For presentation preparation, use the [hackathon demo runbook](docs/DEMO_RUNBOOK.md), which includes preflight checks, the primary judge flow, and a route that remains demonstrable when external services are unavailable.

## Repository Layout

```
frontend/               web UI (Next.js) -- currently the Smart Route Planner demo dashboard
backend/                reserved for a future platform-level API gateway (not implemented yet)
services/
  ai/
    route-planner/       Smart Route Planner -- implemented (FastAPI + XGBoost), see its README
    scenario-simulator/  implemented in route-planner for the MVP
    monitoring/          not implemented yet
    ai-explain/          AI explanation and scoped chatbot service (FastAPI)
  weather/               not implemented yet (BMKG integration currently lives inside route-planner)
  notification/          not implemented yet
  authentication/        not implemented yet
datasets/                shared datasets (empty for now -- route-planner's data lives with it)
docs/                    project-wide docs
infrastructure/          Docker Compose deployment configuration
```

### Implemented modules

The Smart Route Planner is available as a FastAPI + XGBoost backend at
[`services/ai/route-planner/`](services/ai/route-planner/) and the Next.js dashboard at
[`frontend/`](frontend/). See that service's README for setup, Swagger API docs, and known
limitations.

The AI Explain service and scoped cold-chain chatbot are available at
[`services/ai/ai-explain/`](services/ai/ai-explain/). A standalone React interface for the
chatbot is available at [`apps/jagood-web/`](apps/jagood-web/), and planner/scenario results can
also be sent to AI Explain directly from the main dashboard.

## Run the Complete Stack

Docker Compose at the repository root runs PostgreSQL, Smart Route Planner,
the planner dashboard, AI Explain, and the chatbot together. Ollama (the LLM
runtime behind AI Explain) is *not* containerized by default -- see why below.

Optionally copy the environment template and fill in `ORS_API_KEY` for real
OpenRouteService road routing:

```bash
cp .env.example .env
```

### Option A -- native Ollama on the host (recommended on macOS)

Docker Desktop/OrbStack on macOS run Linux containers inside a VM with no access to Metal, so
a containerized Ollama is CPU-only -- workable for a health check, far too slow for interactive
chat (minutes per reply instead of seconds). Running Ollama natively lets it use the host GPU:

```bash
brew install ollama
brew services start ollama
ollama pull qwen3:4b-instruct   # or whatever OLLAMA_MODEL is set to in .env

docker compose up --build
```

`ai-explain` reaches the host's Ollama through `host.docker.internal:11434`.

### Option B -- containerized Ollama (Linux / no local Ollama install)

For a judge/reviewer who'd rather not install anything beyond Docker, CI, or a Linux host with
NVIDIA Container Toolkit GPU passthrough configured, use the override that restores Ollama as a
compose service:

```bash
docker compose -f compose.yaml -f compose.ollama-container.yml up --build
```

This pulls the model into the container on first run (can take several minutes) and works out of
the box, but is CPU-only unless you uncomment the NVIDIA `deploy.resources` block in
[`compose.ollama-container.yml`](compose.ollama-container.yml) on a Linux host with a GPU.

### Both options

- Smart Route Planner: `http://localhost:3000`
- Route Planner API docs: `http://localhost:8000/docs`
- Cold-chain chatbot: `http://localhost:3001`
- AI Explain API docs: `http://localhost:8001/docs`

Run `docker compose down` (add the same `-f` flags as above if you used Option B) to stop the
stack. Port numbers and the Ollama model can be changed in `.env`; see
[`.env.example`](.env.example) for all supported settings.

For standalone chatbot frontend development, keep AI Explain running on port 8001 and run:

```bash
cd apps/jagood-web
npm install
npm run dev
```
