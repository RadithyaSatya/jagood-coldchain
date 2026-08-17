# AI Scenario Simulator

The hackathon MVP is implemented inside the Smart Route Planner service so it
can reuse the same commodity enrichment, environmental data, XGBoost model,
and SHAP explanation pipeline without adding another network boundary.

Use `POST /simulate-scenario` on the route-planner API. It compares a baseline
shipment against changes to delay duration, transport mode, cold-chain
equipment, or insulation quality and returns both model outputs, the risk
delta, affected factors, and a deterministic recommendation.

See the route-planner [README](../route-planner/README.md#scenario-simulator)
for the API contract and current modeling limitations. This directory remains
documentation-only intentionally; extracting a separate microservice is not
needed for the MVP.
