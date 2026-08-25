# JaGOOD Platform API Gateway

FastAPI gateway ini merupakan satu-satunya API publik yang digunakan dashboard
planner dan chatbot. Service Route Planner dan AI Explain tetap modular, tetapi
hanya diakses oleh gateway melalui jaringan internal Docker Compose.

## Endpoint publik

- `GET /health` — health gateway
- `GET /ready` — kesiapan Route Planner dan AI Explain
- `GET /ai-explain/ready` — status LLM dan fallback dari AI Explain
- `GET /commodities` dan `GET /commodities/provenance`
- `POST /predict-route`
- `POST /simulate-scenario`
- `GET|POST|PATCH /shipments...`
- `POST /v1/chat` dan `POST /v1/chat/stream`
- `POST /v1/explanations` dan `POST /v1/explanations/stream`
- `POST /final-recommendation` — orkestrasi route plan dan skenario opsional

## Menjalankan secara lokal

Jalankan Route Planner pada port `8000` dan AI Explain pada port `8001`, lalu:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
```

Konfigurasi tersedia melalui environment variable:

- `ROUTE_PLANNER_BASE_URL` (default `http://localhost:8000`)
- `AI_EXPLAIN_BASE_URL` (default `http://localhost:8001`)
- `GATEWAY_TIMEOUT_SECONDS` (default `300`)
- `GATEWAY_CORS_ORIGINS` (daftar origin dipisahkan koma)

Untuk stack lengkap, gunakan `docker compose up --build` dari root repository.
