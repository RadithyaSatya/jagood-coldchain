import type { RouteCandidate } from "./types";

export function environmentalDataLabel(route: RouteCandidate): string {
  if (route.transport_mode === "darat" && route.environmental_data_quality === "configured") {
    return "asumsi cuaca darat yang telah dikonfigurasi";
  }

  const labels: Record<RouteCandidate["environmental_data_quality"], string> = {
    forecast: "data BMKG untuk kondisi maritim dan pelabuhan",
    partial: "data BMKG yang dilengkapi estimasi cadangan",
    fallback: "estimasi cadangan karena data BMKG tidak tersedia",
    configured: "asumsi lingkungan yang telah dikonfigurasi",
  };
  return labels[route.environmental_data_quality];
}

export function cargoTemperatureDataLabel(route: RouteCandidate): string {
  const labels: Record<RouteCandidate["cargo_temperature_data_quality"], string> = {
    assumed: "pendingin aktif menjaga suhu ideal",
    forecast: "perkiraan Open-Meteo sepanjang rute",
    mixed: "data Open-Meteo yang dilengkapi estimasi suhu",
    synthetic: "estimasi suhu cadangan",
    unavailable: "data suhu lingkungan belum tersedia",
  };
  return labels[route.cargo_temperature_data_quality];
}
