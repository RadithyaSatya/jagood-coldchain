# AI Explain

Implemented FastAPI service for scoped cold-chain explanations and chat. It accepts trusted,
structured results from JaGOOD's analytical pipeline and uses a task-specific LoRA-fine-tuned
Llama 3.2 1B model through Ollama's OpenAI-compatible API to express those facts in Indonesian or
English.

AI Explain does not calculate risk, choose routes, retrieve shipment telemetry, or repair missing
analytical data. Prompts explicitly restrict the model to supplied shipment context or the local
Markdown knowledge base.

## Runtime behavior

- `POST /v1/chat` returns a structured chat response.
- `POST /v1/chat/stream` returns server-sent events.
- `POST /v1/explanations` and `/v1/explanations/stream` support the lower-level explanation contract.
- `GET /health` is process liveness.
- `GET /ready` checks LLM availability and returns `503` with
  `fallback_available: true` when the LLM is unavailable.

Shipment questions require structured `shipment_context`. Unrelated intents are rejected by
deterministic rules before an LLM call. If the LLM times out or fails, chat returns a deterministic
summary using only the supplied facts and recommendation, marked `handled_by: "fallback"`.

## Local setup

```bash
cd services/ai/ai-explain
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/uvicorn ai_explain.main:app --reload --port 8001
```

The default inference endpoint is Ollama's OpenAI-compatible API. Configuration uses the
`AI_EXPLAIN_` environment prefix; see `.env.example` for the model and endpoint settings.

Run tests with:

```bash
.venv/bin/pytest
```

The knowledge base under `knowledge/` uses deterministic keyword retrieval, not embeddings or a
vector database. Retrieved documents provide product information only and never replace the
planner's calculations.

## Fine-tuning evidence

The reproducible training pipeline, deterministic synthetic dataset, held-out evaluation, learned
adapter, and Ollama export instructions are in [`finetuning/`](finetuning/). The checked-in adapter
is the result of genuine LoRA parameter optimization, not prompt engineering. Reported metrics are
limited to the held-out synthetic explanation task and are not evidence of shipment accuracy.

Built with Llama 3.2. Attribution and base-model terms are recorded in
[`finetuning/NOTICE`](finetuning/NOTICE).
