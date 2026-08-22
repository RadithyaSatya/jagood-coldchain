import type { RouteCandidate } from "./types";

export function environmentalDataLabel(route: RouteCandidate): string {
  if (route.transport_mode === "darat" && route.environmental_data_quality === "configured") {
    return "Default darat terkonfigurasi";
  }

  const labels: Record<RouteCandidate["environmental_data_quality"], string> = {
    forecast: "BMKG maritim & pelabuhan",
    partial: "BMKG sebagian + fallback",
    fallback: "Fallback netral (BMKG tidak tersedia)",
    configured: "Default terkonfigurasi",
  };
  return labels[route.environmental_data_quality];
}

export function cargoTemperatureDataLabel(route: RouteCandidate): string {
  const labels: Record<RouteCandidate["cargo_temperature_data_quality"], string> = {
    assumed: "Asumsi reefer di suhu ideal",
    forecast: "Open-Meteo sepanjang rute",
    mixed: "Open-Meteo + fallback sintetis",
    synthetic: "Fallback suhu sintetis",
    unavailable: "Suhu ambient tidak tersedia",
  };
  return labels[route.cargo_temperature_data_quality];
}
