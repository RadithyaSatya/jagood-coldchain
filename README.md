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
    ai-explain/          not implemented yet
  weather/               not implemented yet (BMKG integration currently lives inside route-planner)
  notification/          not implemented yet
  authentication/        not implemented yet
datasets/                shared datasets (empty for now -- route-planner's data lives with it)
docs/                    project-wide docs
infrastructure/          deployment config (Docker/CI/CD) -- not implemented yet
```

### Smart Route Planner: implementation status

The only implemented module so far. Fully working end-to-end: FastAPI + XGBoost backend at
[`services/ai/route-planner/`](services/ai/route-planner/) and the Next.js dashboard at
[`frontend/`](frontend/). See that service's README for setup, Swagger API docs, and known
limitations.
