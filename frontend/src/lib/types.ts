export interface Commodity {
  commodity_type: string;
  temp_ideal_min_c: number;
  temp_ideal_max_c: number;
  shelf_life_hours_at_ideal_temp: number;
  delay_tolerance_hours: number;
  temp_sensitivity_level: string;
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
