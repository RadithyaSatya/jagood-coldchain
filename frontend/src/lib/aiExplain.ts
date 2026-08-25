import type { RouteCandidate, ScenarioResponse } from "@/lib/types";
import { cargoTemperatureDataLabel, environmentalDataLabel } from "@/lib/dataProvenance";

export type AIExplainSource = "smart_route_planner" | "scenario_simulator";
export type AIExplainRiskLevel = "low" | "medium" | "high" | "critical" | "unknown";

export interface AIExplainContext {
  shipment_id?: string;
  source: AIExplainSource;
  product: string;
  facts: Record<string, string | number | boolean>;
  risk_level: AIExplainRiskLevel;
  recommendation?: string;
}

const SCENARIO_FACTOR_LABELS: Record<string, string> = {
  expected_delay_hours: "Keterlambatan tambahan",
  transport_mode: "Moda transportasi",
  cold_chain_equipment: "Peralatan cold chain",
  insulation_quality: "Kualitas insulasi",
  max_cargo_temp_excess_c: "Paparan suhu di atas batas ideal",
  distance_km: "Jarak rute",
  wave_height_m: "Tinggi gelombang",
  weather_condition: "Kondisi cuaca",
};

function formatScenarioFactorValue(factor: string, value: number | string): string {
  if (typeof value !== "number") return value;
  if (factor.endsWith("_hours")) return `${value.toFixed(1)} jam`;
  if (factor.endsWith("_km")) return `${value.toFixed(1)} km`;
  if (factor.endsWith("_c")) return `${value.toFixed(1)}°C`;
  if (factor === "wave_height_m") return `${value.toFixed(2)} m`;
  return value.toFixed(2);
}

function normalizeRiskLevel(value: string): AIExplainRiskLevel {
  const normalized = value.toLowerCase();
  if (normalized === "low" || normalized === "medium" || normalized === "high" || normalized === "critical") {
    return normalized;
  }
  return "unknown";
}

function formatShapFactors(route: RouteCandidate): string {
  return route.risk_explanation_factors
    .slice(0, 3)
    .map((factor) => `${factor.factor}: ${factor.effect} (impact ${factor.impact})`)
    .join("; ")
    .slice(0, 500);
}

export function buildRouteExplainContext(
  shipmentId: string,
  product: string,
  route: RouteCandidate,
): AIExplainContext {
  const shapFactors = formatShapFactors(route);
  return {
    shipment_id: shipmentId,
    source: "smart_route_planner",
    product,
    risk_level: normalizeRiskLevel(route.risk_level),
    facts: {
      route_id: route.route_id,
      transport_mode: route.transport_mode,
      distance: `${route.distance_km.toFixed(1)} km`,
      travel_duration: `${route.estimated_duration_hours.toFixed(1)} jam`,
      expected_delay: `${route.expected_delay_hours.toFixed(1)} jam`,
      risk_probability: `${(route.risk_probability * 100).toFixed(2)}%`,
      model_confidence: `${(route.confidence_score * 100).toFixed(2)}%`,
      weather_condition: route.weather_condition,
      wave_condition: `${route.wave_category}, ${route.wave_height_m.toFixed(2)} m`,
      wind_speed: `${route.wind_speed_kmh.toFixed(1)} km/jam`,
      cargo_temp_excess: `${route.max_cargo_temp_excess_c.toFixed(1)}°C`,
      cold_chain_equipment: route.cold_chain_equipment,
      data_quality: route.data_quality,
      environmental_data_quality: route.environmental_data_quality,
      environmental_data_source: environmentalDataLabel(route),
      cargo_temperature_data_quality: route.cargo_temperature_data_quality,
      cargo_temperature_source: cargoTemperatureDataLabel(route),
      ...(route.baseline_delay_hours !== undefined
        ? { baseline_delay: `${route.baseline_delay_hours.toFixed(1)} jam` }
        : {}),
      ...(route.scenario_delay_hours !== undefined
        ? { scenario_delay: `${route.scenario_delay_hours.toFixed(1)} jam` }
        : {}),
      ...(route.delay_data_quality ? { delay_data_quality: route.delay_data_quality } : {}),
      ...(route.estimated_remaining_shelf_life_hours !== undefined
        ? { estimated_remaining_shelf_life: `${route.estimated_remaining_shelf_life_hours.toFixed(1)} jam` }
        : {}),
      ...(route.estimated_remaining_shelf_life_percent !== undefined
        ? { estimated_remaining_shelf_life_percent: `${route.estimated_remaining_shelf_life_percent.toFixed(1)}%` }
        : {}),
      ...(route.quality_retention_proxy !== undefined
        ? { quality_retention_proxy: `${route.quality_retention_proxy.toFixed(1)}%` }
        : {}),
      ...(route.quality_estimation_data_quality
        ? { quality_estimation_data_quality: route.quality_estimation_data_quality }
        : {}),
      remaining_shelf_life: `${route.remaining_shelf_life_hours.toFixed(1)} jam (${route.remaining_shelf_life_pct.toFixed(0)}%)`,
      quality_status: route.quality_status,
      shap_summary: route.risk_explanation_summary,
      ...(shapFactors ? { shap_factors: shapFactors } : {}),
    },
  };
}

export function buildScenarioExplainContext(
  shipmentId: string,
  product: string,
  scenario: ScenarioResponse,
): AIExplainContext {
  const affectedFactors = scenario.affected_factors
    .map(
      (factor) =>
        `${SCENARIO_FACTOR_LABELS[factor.factor] ?? factor.factor}: ${formatScenarioFactorValue(factor.factor, factor.baseline_value)} → ${formatScenarioFactorValue(factor.factor, factor.simulated_value)}`,
    )
    .join("; ")
    .slice(0, 500);
  const shapFactors = formatShapFactors(scenario.simulated);

  return {
    shipment_id: shipmentId,
    source: "scenario_simulator",
    product,
    risk_level: normalizeRiskLevel(scenario.simulated.risk_level),
    recommendation: scenario.recommendation,
    facts: {
      scenario_id: scenario.scenario_id,
      baseline_risk_level: scenario.baseline.risk_level,
      baseline_risk_probability: `${(scenario.baseline.risk_probability * 100).toFixed(2)}%`,
      simulated_risk_level: scenario.simulated.risk_level,
      simulated_risk_probability: `${(scenario.simulated.risk_probability * 100).toFixed(2)}%`,
      risk_delta: `${(scenario.risk_delta * 100).toFixed(2)} poin persentase`,
      expected_delay: `${scenario.simulated.expected_delay_hours.toFixed(1)} jam`,
      simulated_transport_mode: scenario.simulated.transport_mode,
      simulated_cold_chain_equipment: scenario.simulated.cold_chain_equipment,
      simulated_cargo_temp_excess: `${scenario.simulated.max_cargo_temp_excess_c.toFixed(1)}°C`,
      environmental_data_quality: scenario.simulated.environmental_data_quality,
      environmental_data_source: environmentalDataLabel(scenario.simulated),
      cargo_temperature_data_quality: scenario.simulated.cargo_temperature_data_quality,
      cargo_temperature_source: cargoTemperatureDataLabel(scenario.simulated),
      ...(scenario.simulated.baseline_delay_hours !== undefined
        ? { baseline_delay: `${scenario.simulated.baseline_delay_hours.toFixed(1)} jam` }
        : {}),
      ...(scenario.simulated.scenario_delay_hours !== undefined
        ? { scenario_delay: `${scenario.simulated.scenario_delay_hours.toFixed(1)} jam` }
        : {}),
      ...(scenario.simulated.estimated_remaining_shelf_life_hours !== undefined
        ? {
            estimated_remaining_shelf_life: `${scenario.simulated.estimated_remaining_shelf_life_hours.toFixed(1)} jam`,
          }
        : {}),
      ...(scenario.simulated.estimated_remaining_shelf_life_percent !== undefined
        ? {
            estimated_remaining_shelf_life_percent: `${scenario.simulated.estimated_remaining_shelf_life_percent.toFixed(1)}%`,
          }
        : {}),
      ...(scenario.simulated.quality_retention_proxy !== undefined
        ? { quality_retention_proxy: `${scenario.simulated.quality_retention_proxy.toFixed(1)}%` }
        : {}),
      ...(scenario.simulated.quality_estimation_data_quality
        ? { quality_estimation_data_quality: scenario.simulated.quality_estimation_data_quality }
        : {}),
      baseline_remaining_shelf_life: `${scenario.baseline.remaining_shelf_life_hours.toFixed(1)} jam (${scenario.baseline.remaining_shelf_life_pct.toFixed(0)}%)`,
      simulated_remaining_shelf_life: `${scenario.simulated.remaining_shelf_life_hours.toFixed(1)} jam (${scenario.simulated.remaining_shelf_life_pct.toFixed(0)}%)`,
      simulated_quality_status: scenario.simulated.quality_status,
      ...(affectedFactors ? { affected_factors: affectedFactors } : {}),
      shap_summary: scenario.simulated.risk_explanation_summary,
      ...(shapFactors ? { shap_factors: shapFactors } : {}),
    },
  };
}
