import { buildRouteExplainContext, buildScenarioExplainContext } from "@/lib/aiExplain";
import { cargoTemperatureDataLabel, environmentalDataLabel } from "@/lib/dataProvenance";
import type {
  FinalRecommendationResponse,
  PredictRouteResponse,
  RouteRequestPayload,
  ScenarioChangesPayload,
  ScenarioResponse,
} from "@/lib/types";

const ROUTE_PLANNER_API_BASE_URL =
  process.env.ROUTE_PLANNER_API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

interface FinalRecommendationRequest {
  shipment: RouteRequestPayload;
  scenario_changes?: ScenarioChangesPayload;
}

class PlannerRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function plannerRequest<T>(path: string, payload: object): Promise<T> {
  const response = await fetch(`${ROUTE_PLANNER_API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
    signal: AbortSignal.timeout(60_000),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === "string" ? error.detail : `Route planner gagal (HTTP ${response.status})`;
    throw new PlannerRequestError(detail, response.status);
  }
  return (await response.json()) as T;
}

function isRequest(value: unknown): value is FinalRecommendationRequest {
  if (typeof value !== "object" || value === null) return false;
  const shipment = (value as Record<string, unknown>).shipment;
  return typeof shipment === "object" && shipment !== null;
}

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return Response.json({ detail: "Request body must be valid JSON." }, { status: 400 });
  }

  if (!isRequest(payload)) {
    return Response.json({ detail: "Field shipment wajib diisi." }, { status: 422 });
  }

  try {
    const routePlan = await plannerRequest<PredictRouteResponse>("/predict-route", payload.shipment);
    const scenario = payload.scenario_changes
      ? await plannerRequest<ScenarioResponse>("/simulate-scenario", {
          baseline: { ...payload.shipment, shipment_id: routePlan.shipment_id },
          changes: payload.scenario_changes,
        })
      : null;
    const route = routePlan.recommended_route;
    const recommendation =
      scenario?.recommendation ??
      `Gunakan rute ${route.route_id} berdasarkan preferensi ${payload.shipment.ranking_preference}.`;

    const response: FinalRecommendationResponse = {
      route_plan: routePlan,
      scenario,
      final_recommendation: {
        route_id: route.route_id,
        risk_level: route.risk_level,
        risk_probability: route.risk_probability,
        recommendation,
        provenance: {
          routing: route.data_quality,
          environment: environmentalDataLabel(route),
          cargo_temperature: cargoTemperatureDataLabel(route),
        },
      },
      explanation_context: scenario
        ? buildScenarioExplainContext(routePlan.shipment_id, payload.shipment.commodity_type, scenario)
        : buildRouteExplainContext(routePlan.shipment_id, payload.shipment.commodity_type, route),
    };
    return Response.json(response);
  } catch (error) {
    const detail = error instanceof Error ? error.message : "Final Recommendation gagal diproses.";
    const status =
      error instanceof PlannerRequestError
        ? error.status >= 400 && error.status < 500
          ? error.status
          : 502
        : error instanceof DOMException && error.name === "TimeoutError"
          ? 504
          : 502;
    return Response.json({ detail }, { status });
  }
}
