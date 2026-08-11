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
curl http://localhost:8000/v1/chat \
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

## Run the Jagood Web App

Start the complete stack from the repository root:

```bash
docker compose up --build
```

Open `http://localhost:3000` for the Jagood React application. The first available module is the
cold-chain chatbot; the app structure can also host monitoring, simulation, and planning modules
later. The web container proxies `/api` requests to the AI service, so no browser CORS
configuration is required. Set `JAGOOD_WEB_PORT` to expose the application on a different port.

For frontend development, keep the API running on port 8000 and run:

```bash
cd apps/jagood-web
npm install
npm run dev
```
