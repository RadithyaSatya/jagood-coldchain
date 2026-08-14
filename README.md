# Jagood ColdChain

Jagood ColdChain is an AI-powered solution designed to make cold-chain food delivery safer, more efficient, and easier to monitor.

Food products such as fresh produce, seafood, dairy, meat, and frozen goods require stable temperatures throughout their journey. Route changes, delays, or transportation disruptions can reduce food quality, shorten shelf life, and cause significant losses. Jagood ColdChain helps users identify these risks earlier and make better-informed decisions.

## Key Features

### Smart Route Planner

Recommends delivery routes by considering travel efficiency and potential risks to food quality throughout the distribution process.

### AI Scenario Simulator

Allows users to explore delivery scenarios such as delays, route changes, and temperature disruptions before a shipment begins.

### Transportation Monitoring

Monitors shipment journeys and conditions to help detect potential issues at an early stage.

### AI Explain

Explains recommendations, risks, and simulation results in clear language so users can make decisions with greater confidence.

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
      "source": "transportation_monitoring",
      "product": "Frozen tuna",
      "facts": {"current_temperature": "-16 °C"},
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

- Reduce the risk of food spoilage during delivery.
- Support more effective distribution planning.
- Provide early warnings for potential disruptions.
- Enable decision-making based on clear and relevant information.
- Improve transparency across the cold-chain transportation process.

## Project Status

Jagood ColdChain is currently being developed as a hackathon project, with an initial focus on validating its AI-powered features and user experience.

## Repository Layout

```
frontend/               web UI (Next.js) -- currently the Smart Route Planner demo dashboard
backend/                reserved for a future platform-level API gateway (not implemented yet)
services/
  ai/
    route-planner/       Smart Route Planner -- implemented (FastAPI + XGBoost), see its README
    scenario-simulator/  not implemented yet
    monitoring/          not implemented yet
    ai-explain/          AI explanation and scoped chatbot service (FastAPI)
  weather/               not implemented yet (BMKG integration currently lives inside route-planner)
  notification/          not implemented yet
  authentication/        not implemented yet
datasets/                shared datasets (empty for now -- route-planner's data lives with it)
docs/                    project-wide docs
infrastructure/          deployment config (Docker/CI/CD) -- not implemented yet
```

### Implemented modules

The Smart Route Planner is available as a FastAPI + XGBoost backend at
[`services/ai/route-planner/`](services/ai/route-planner/) and the Next.js dashboard at
[`frontend/`](frontend/). See that service's README for setup, Swagger API docs, and known
limitations.

The AI Explain service and scoped cold-chain chatbot are available at
[`services/ai/ai-explain/`](services/ai/ai-explain/). A standalone React interface for the
chatbot is available at [`apps/jagood-web/`](apps/jagood-web/) while frontend integration is in
progress.

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
