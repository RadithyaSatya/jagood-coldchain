# JaGOOD (Jaga Food) ColdChain

JaGOOD is an AI-powered decision-support MVP for planning cold-chain food delivery. It helps a user compare route candidates, estimate shipment risk, simulate a disruption, and understand the recommendation before dispatch.

The project addresses COMPFEST 18 AI Innovation Challenge's **Smart Logistics** area. Its core AI pipeline combines an XGBoost risk classifier, SHAP-based prediction explanations, deterministic route and scenario calculations, and a task-specific LoRA-fine-tuned Llama 3.2 1B explanation layer.

## Core MVP Flow

```text
Shipment input
    -> route candidates and environmental enrichment
    -> XGBoost risk inference and SHAP factors
    -> risk-based route recommendation
    -> optional deterministic scenario comparison
    -> grounded natural-language explanation
```

The submission demo focuses on this synchronous flow. JaGOOD is not a production navigation, food-safety certification, continuous GPS/IoT tracking, or real-time fleet-monitoring system.

## Core Features

- **Smart Route Planner:** ranks land or multimodal route candidates by estimated cold-chain risk or travel time.
- **Cold-Chain Risk Prediction:** classifies each candidate as `Low`, `Medium`, or `High` using a saved XGBoost model.
- **SHAP Explainability:** reports the factors that tend to raise or lower each model prediction.
- **Scenario Simulator:** compares the baseline against changes in delay, transport mode, cooling equipment, or insulation.
- **Quality Proxy:** estimates remaining shelf life using a Q10-based temperature-exposure calculation.
- **AI Explain:** uses a LoRA-fine-tuned Llama 3.2 1B model to explain structured analytical results. A deterministic fallback is available when the local LLM is unavailable.

## AI and Data Scope

- The XGBoost model is trained on synthetic shipment data and synthetic labels. Its output demonstrates the inference pipeline and supports relative route comparison; it is not a validated probability of real-world spoilage.
- Commodity storage temperatures and shelf-life values include field-level provenance. Some delay-tolerance and temperature-sensitivity values remain documented MVP assumptions.
- BMKG is used for maritime and port conditions, while Open-Meteo is used for land weather and ambient temperature. Clearly labelled fallback values keep the local demo operational when an external API is unavailable.
- Route and risk calculations are owned by the analytical engine. The language model explains those results and does not invent route or risk values.
- LoRA training data, configuration, adapter weights, and held-out evaluation results are included in [`services/ai/ai-explain/finetuning/`](services/ai/ai-explain/finetuning/).

## Architecture

```text
Planner UI
    -> FastAPI Platform Gateway
        -> Route Planner (routing, XGBoost, SHAP, scenario, quality proxy)
        -> AI Explain (fine-tuned Llama adapter or deterministic fallback)
        -> PostgreSQL
```

All frontend requests go through the FastAPI Platform Gateway. The Route Planner and AI Explain services remain separate internal modules and are packaged with Docker Compose for local reproduction.

## Repository Layout

```text
frontend/                         Next.js planner interface
backend/                          FastAPI platform gateway
services/ai/route-planner/        routing and analytical inference service
services/ai/ai-explain/           explanation service and LoRA artifacts
apps/jagood-web/                  optional cold-chain chatbot interface
tests/golden_demo/                deterministic offline core-flow test
compose.yaml                      default local stack
compose.ollama-container.yml      Docker-only Ollama override
```

## Quick Start with Docker Compose

### Requirements

- Docker Engine or Docker Desktop with Docker Compose v2
- At least 8 GB RAM recommended
- Internet access on the first run to download container images and the Llama 3.2 1B base model
- An OpenRouteService API key is optional; the planner has a labelled routing fallback

### Option 1: Docker-only setup

This option requires only Docker and includes Ollama in the Compose stack.

```bash
git clone https://github.com/RadithyaSatya/jagood-coldchain.git
cd jagood-coldchain
cp .env.example .env
docker compose -f compose.yaml -f compose.ollama-container.yml up --build
```

The first run downloads the base model and creates `llama-jagood-ai-explain:latest` from the checked-in LoRA adapter, so startup can take several minutes. On macOS, containerized inference uses the CPU and may respond slowly; the native Ollama option below is recommended for an interactive demonstration.

### Option 2: Native Ollama on macOS

Running Ollama natively allows it to use Apple Metal acceleration.

```bash
brew install ollama
brew services start ollama

git clone https://github.com/RadithyaSatya/jagood-coldchain.git
cd jagood-coldchain
cp .env.example .env
bash services/ai/ai-explain/finetuning/export_ollama.sh
docker compose up --build
```

The export script creates `llama-jagood-ai-explain:latest` from the included adapter. Training is not required to run the demonstration.

### OpenRouteService configuration

The competition `.env.example` includes a shared, quota-limited demo key for live road geometry, so no additional routing credential is required during judging. If the demo key is unavailable or has exhausted its quota, the application remains usable through its labelled distance and route fallback.

Do not add personal or production credentials to the repository. The shared competition key must be rotated after judging.

## Verify the Running MVP

Wait until all services are healthy:

```bash
docker compose ps
curl http://localhost:8080/ready
```

When using the Docker-only option, include both Compose files in the `ps` command:

```bash
docker compose -f compose.yaml -f compose.ollama-container.yml ps
```

Open the core interfaces:

- Planner MVP: `http://localhost:3000`
- FastAPI Gateway and Swagger: `http://localhost:8080/docs`
- Optional chatbot: `http://localhost:3001`

Recommended core demonstration:

1. Enter the origin, destination, commodity, transport preference, and cold-chain conditions.
2. Generate and compare the recommended route and alternatives.
3. Review the predicted risk, confidence, data provenance, and SHAP factors.
4. Change delay or cold-chain conditions in the Scenario Simulator.
5. Compare the baseline and simulated risk, then request an AI explanation.

## Stop the Stack

For the default native-Ollama setup:

```bash
docker compose down
```

For the Docker-only setup:

```bash
docker compose -f compose.yaml -f compose.ollama-container.yml down
```

These commands retain the PostgreSQL and Ollama volumes. Add `--volumes` only when stored local data and downloaded models are no longer needed.

## Validation

Validate the Compose configuration:

```bash
docker compose config --quiet
docker compose -f compose.yaml -f compose.ollama-container.yml config --quiet
```

The repository also includes automated tests for the Route Planner, AI Explain service, platform gateway, and deterministic offline golden demo. The GitHub Actions workflow runs these checks on `main` and pull requests.

## Known MVP Limitations

- Model-risk metrics measure learning on synthetic labels, not field performance.
- Route output is decision support, not official navigation guidance.
- The Q10 result is a quality-retention proxy, not a food-safety guarantee or certified expiry estimate.
- Port condition flags indicate environmental risk and are not official port-closure status.
- External routing and weather services can fail or rate-limit requests; labelled fallbacks are provided.
- The first uncached route request can be slower than subsequent requests.
- Authentication, notifications, continuous telemetry, and operational validation with real shipment outcomes are outside the core submission demo.

## Development History

All competition work is maintained in the public GitHub repository. Commit messages should follow Conventional Commits, for example:

```text
feat: add route risk comparison
fix: handle unavailable weather service
refactor: simplify scenario calculation
```
