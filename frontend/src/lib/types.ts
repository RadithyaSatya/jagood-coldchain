export type DataClassification = "REAL" | "REFERENCE" | "DERIVED" | "SYNTHETIC" | "DEMO";

export interface CommodityFieldProvenance {
  classification: DataClassification;
  source_ids: string[];
  method: string;
}

export interface Commodity {
  commodity_type: string;
  temp_ideal_min_c: number;
  temp_ideal_max_c: number;
  shelf_life_hours_at_ideal_temp: number;
  delay_tolerance_hours: number;
  temp_sensitivity_level: string;
  provenance: {
    record_classification: DataClassification;
    source_ids: string[];
    fields: Record<string, CommodityFieldProvenance>;
  };
}

export interface RiskHotspot {
  lat: number;
  lon: number;
}

export interface PortInfo {
  port_name: string;
  lat: number;
  lon: number;
}

export interface PortPairInfo {
  embark: PortInfo;
  disembark: PortInfo;
}

export interface RiskFactor {
  factor: string;
  effect: "menaikkan" | "menurunkan";
  impact: number;
}

export interface CargoTempPoint {
  hour: number;
  temp_c: number;
}

export interface RouteCandidate {
  route_id: string;
  transport_mode: string;
  distance_km: number;
  estimated_duration_hours: number;
  expected_delay_hours: number;
  baseline_delay_hours?: number;
  scenario_delay_hours?: number;
  delay_data_quality?: DataClassification;
  estimated_arrival: string;

  risk_level: string;
  risk_probability: number;
  confidence_score: number;
  trigger_reason: string | null;
  data_quality: string;
  environmental_data_quality: "forecast" | "partial" | "fallback" | "configured";

  wave_category: string;
  wave_height_m: number;
  wind_speed_kmh: number;
  weather_condition: string;
  port_status_flag: number;
  port_ambient_temp_c: number;
  historical_delay_avg_hours: number;
  historical_damage_rate: number;

  cold_chain_equipment: string;
  commodity_temp_ideal_c: number;
  max_cargo_temp_excess_c: number;
  cargo_temp_profile: CargoTempPoint[];
  cargo_temperature_data_quality: "assumed" | "forecast" | "mixed" | "synthetic" | "unavailable";
  effective_shelf_life_consumed_hours?: number;
  estimated_remaining_shelf_life_hours?: number;
  estimated_remaining_shelf_life_percent?: number;
  quality_retention_proxy?: number;
  quality_estimation_data_quality?: string;

  geometry: [number, number][];
  risk_hotspot: RiskHotspot | null;
  port_pair: PortPairInfo | null;

  risk_explanation_summary: string;
  risk_explanation_factors: RiskFactor[];
}

export interface PredictRouteResponse {
  shipment_id: string;
  recommended_route: RouteCandidate;
  alternative_routes: RouteCandidate[];
}

export type TransportModePreference = "darat" | "laut" | "kombinasi" | "semua";
export type ColdChainEquipment = "reefer" | "pasif";
export type InsulationQuality = "baik" | "sedang" | "buruk";
export type RankingPreference = "risiko" | "kecepatan";

export interface RouteRequestPayload {
  shipment_id?: string;
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  commodity_type: string;
  departure_time: string;
  transport_mode_preference: TransportModePreference;
  cold_chain_equipment: ColdChainEquipment;
  insulation_quality: InsulationQuality;
  ranking_preference: RankingPreference;
}

export interface ScenarioFactorChange {
  factor: string;
  baseline_value: number | string;
  simulated_value: number | string;
}

export interface ScenarioResponse {
  scenario_id: string;
  baseline: RouteCandidate;
  simulated: RouteCandidate;
  risk_delta: number;
  affected_factors: ScenarioFactorChange[];
  recommendation: string;
}

export interface City {
  label: string;
  lat: number;
  lon: number;
}
