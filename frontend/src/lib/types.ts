export interface Commodity {
  commodity_type: string;
  temp_ideal_min_c: number;
  temp_ideal_max_c: number;
  shelf_life_hours_at_ideal_temp: number;
  delay_tolerance_hours: number;
  temp_sensitivity_level: string;
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

  risk_level: string;
  risk_probability: number;
  confidence_score: number;
  trigger_reason: string | null;
  data_quality: string;

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

export interface City {
  label: string;
  lat: number;
  lon: number;
}
