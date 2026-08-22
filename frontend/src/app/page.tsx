"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import AIExplainPanel from "@/components/AIExplainPanel";
import CargoTempChart from "@/components/CargoTempChart";
import FinalRecommendation from "@/components/FinalRecommendation";
import ParameterLegend from "@/components/ParameterLegend";
import ProductQualitySummary from "@/components/ProductQualitySummary";
import RiskBadge from "@/components/RiskBadge";
import RiskExplanation from "@/components/RiskExplanation";
import RouteComparison from "@/components/RouteComparison";
import ScenarioSimulator from "@/components/ScenarioSimulator";
import { buildRouteExplainContext } from "@/lib/aiExplain";
import { CITIES } from "@/lib/cities";
import { environmentalDataLabel } from "@/lib/dataProvenance";
import type {
  City,
  ColdChainEquipment,
  Commodity,
  InsulationQuality,
  PredictRouteResponse,
  RankingPreference,
  RouteCandidate,
  RouteRequestPayload,
  ScenarioResponse,
  TransportModePreference,
} from "@/lib/types";

const RouteMap = dynamic(() => import("@/components/RouteMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-sm text-zinc-500 dark:text-zinc-400">
      Memuat peta...
    </div>
  ),
});

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const MODE_LABELS: Record<string, string> = {
  darat: "Darat",
  laut: "Laut",
  kombinasi: "Kombinasi (Darat + Laut)",
};

function defaultDepartureTime(): string {
  const d = new Date(Date.now() + 24 * 3600 * 1000);
  d.setMinutes(0, 0, 0);
  return d.toISOString().slice(0, 16);
}

function formatCoord(lat: number, lon: number): string {
  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
}

function formatArrival(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function AlternativeRouteCard({
  candidate,
  selected,
  onSelect,
}: {
  candidate: RouteCandidate;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`cursor-pointer rounded-lg border bg-white p-4 transition-colors dark:bg-zinc-900 ${
        selected
          ? "border-2 border-sky-500 dark:border-sky-500"
          : "border-zinc-200 hover:border-sky-300 dark:border-zinc-800 dark:hover:border-sky-800"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">{MODE_LABELS[candidate.transport_mode] ?? candidate.transport_mode}</span>
        <RiskBadge level={candidate.risk_level} />
      </div>
      <div className="mt-1 grid grid-cols-2 gap-2 text-sm text-zinc-600 sm:grid-cols-3 dark:text-zinc-400">
        <div>Jarak: {candidate.distance_km.toFixed(0)} km</div>
        <div>Estimasi: {candidate.estimated_duration_hours.toFixed(1)} jam</div>
        <div>Tiba: {formatArrival(candidate.estimated_arrival)}</div>
        <div>Skor: {(candidate.risk_probability * 100).toFixed(0)}%</div>
        <div>Routing: {candidate.data_quality === "estimated" ? "Fallback estimasi" : "Tanpa fallback"}</div>
        <div>Lingkungan: {environmentalDataLabel(candidate)}</div>
      </div>
      <RiskExplanation summary={candidate.risk_explanation_summary} factors={candidate.risk_explanation_factors} />
      <CargoTempChart route={candidate} />
      <ProductQualitySummary route={candidate} />
    </div>
  );
}

export default function Home() {
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [origin, setOrigin] = useState<City>(CITIES[0]);
  const [destination, setDestination] = useState<City>(CITIES[1]);
  const [pickMode, setPickMode] = useState<"origin" | "destination">("origin");
  const [commodityType, setCommodityType] = useState("");
  const [departureTime, setDepartureTime] = useState(defaultDepartureTime());
  const [transportModePreference, setTransportModePreference] = useState<TransportModePreference>("semua");
  const [coldChainEquipment, setColdChainEquipment] = useState<ColdChainEquipment>("reefer");
  const [insulationQuality, setInsulationQuality] = useState<InsulationQuality>("sedang");
  const [rankingPreference, setRankingPreference] = useState<RankingPreference>("risiko");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictRouteResponse | null>(null);
  const [resultRequest, setResultRequest] = useState<RouteRequestPayload | null>(null);
  // The preference the displayed result was actually produced with -- kept
  // separate from rankingPreference so changing the selector without
  // re-submitting can't mislabel how the listed routes were ordered.
  const [resultRanking, setResultRanking] = useState<"risiko" | "kecepatan">("risiko");
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResponse | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/commodities`)
      .then((res) => res.json())
      .then((data: Commodity[]) => {
        setCommodities(data);
        if (data.length > 0) setCommodityType(data[0].commodity_type);
      })
      .catch(() => setError("Tidak bisa memuat daftar komoditas dari backend."));
  }, []);

  function handleOriginChange(lat: number, lon: number) {
    setOrigin({ label: formatCoord(lat, lon), lat, lon });
  }
  function handleDestinationChange(lat: number, lon: number) {
    setDestination({ label: formatCoord(lat, lon), lat, lon });
  }

  const originPresetIdx = CITIES.findIndex((c) => c.lat === origin.lat && c.lon === origin.lon);
  const destinationPresetIdx = CITIES.findIndex((c) => c.lat === destination.lat && c.lon === destination.lon);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setResultRequest(null);
    setScenarioResult(null);

    try {
      const requestPayload: RouteRequestPayload = {
        origin: { lat: origin.lat, lon: origin.lon },
        destination: { lat: destination.lat, lon: destination.lon },
        commodity_type: commodityType,
        departure_time: new Date(departureTime).toISOString(),
        transport_mode_preference: transportModePreference,
        cold_chain_equipment: coldChainEquipment,
        insulation_quality: insulationQuality,
        ranking_preference: rankingPreference,
      };
      const res = await fetch(`${API_BASE}/predict-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestPayload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Request gagal (HTTP ${res.status})`);
      }

      const data: PredictRouteResponse = await res.json();
      setResult(data);
      setResultRequest({ ...requestPayload, shipment_id: data.shipment_id });
      setResultRanking(rankingPreference);
      setSelectedRouteId(data.recommended_route.route_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan tak terduga.");
    } finally {
      setLoading(false);
    }
  }

  const allRoutes = result ? [result.recommended_route, ...result.alternative_routes] : [];

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div className="w-full max-w-5xl">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
          JaGOOD Smart Route Planner
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Rute diurutkan berdasarkan risiko kerusakan produk terendah (bukan sekadar tercepat), dengan analisis
          cold chain untuk setiap rute -- klik rute di peta atau di daftar untuk membandingkan.
        </p>

        <div className="mt-6">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setPickMode("origin")}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                pickMode === "origin"
                  ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
              }`}
            >
              A Titik Asal: {origin.label}
            </button>
            <button
              type="button"
              onClick={() => setPickMode("destination")}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                pickMode === "destination"
                  ? "bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700"
              }`}
            >
              B Titik Tujuan: {destination.label}
            </button>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">
              Klik tombol lalu klik peta untuk menandai titik, atau seret penanda A/B langsung.
            </span>
          </div>
          <div className="h-[420px] overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
            <RouteMap
              origin={origin}
              destination={destination}
              onOriginChange={handleOriginChange}
              onDestinationChange={handleDestinationChange}
              pickMode={pickMode}
              routes={allRoutes}
              recommendedRouteId={result?.recommended_route.route_id}
              selectedRouteId={selectedRouteId ?? undefined}
              onSelectRoute={setSelectedRouteId}
            />
          </div>
        </div>

        <form
          onSubmit={handleSubmit}
          className="mt-4 grid grid-cols-1 gap-4 rounded-lg border border-zinc-200 bg-white p-5 sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <label className="flex flex-col gap-1 text-sm">
            Asal (atau pilih di peta)
            <select
              value={originPresetIdx === -1 ? "" : originPresetIdx}
              onChange={(e) => setOrigin(CITIES[Number(e.target.value)])}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="" disabled hidden>
                -- titik kustom dari peta --
              </option>
              {CITIES.map((city, i) => (
                <option key={city.label} value={i}>
                  {city.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Tujuan (atau pilih di peta)
            <select
              value={destinationPresetIdx === -1 ? "" : destinationPresetIdx}
              onChange={(e) => setDestination(CITIES[Number(e.target.value)])}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="" disabled hidden>
                -- titik kustom dari peta --
              </option>
              {CITIES.map((city, i) => (
                <option key={city.label} value={i}>
                  {city.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Jenis Komoditas
            <select
              value={commodityType}
              onChange={(e) => setCommodityType(e.target.value)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              {commodities.map((c) => (
                <option key={c.commodity_type} value={c.commodity_type}>
                  {c.commodity_type}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Waktu Keberangkatan
            <input
              type="datetime-local"
              value={departureTime}
              onChange={(e) => setDepartureTime(e.target.value)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Preferensi Moda Transportasi
            <select
              value={transportModePreference}
              onChange={(e) => setTransportModePreference(e.target.value as TransportModePreference)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="semua">Semua</option>
              <option value="darat">Darat saja</option>
              <option value="laut">Laut saja</option>
              <option value="kombinasi">Kombinasi</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Urutkan Rute Berdasarkan
            <select
              value={rankingPreference}
              onChange={(e) => setRankingPreference(e.target.value as RankingPreference)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="risiko">Risiko kerusakan terendah</option>
              <option value="kecepatan">Waktu tempuh tercepat</option>
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Peralatan Cold Chain
            <select
              value={coldChainEquipment}
              onChange={(e) => setColdChainEquipment(e.target.value as ColdChainEquipment)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="reefer">Reefer (pendingin aktif)</option>
              <option value="pasif">Pasif (tanpa pendingin aktif)</option>
            </select>
          </label>

          {coldChainEquipment === "pasif" && (
            <label className="flex flex-col gap-1 text-sm sm:col-span-2">
              Kualitas Insulasi Kemasan
              <select
                value={insulationQuality}
                onChange={(e) => setInsulationQuality(e.target.value as InsulationQuality)}
                className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
              >
                <option value="baik">Baik (cooler box tebal)</option>
                <option value="sedang">Sedang (styrofoam standar)</option>
                <option value="buruk">Buruk (kardus/insulasi tipis)</option>
              </select>
            </label>
          )}

          <button
            type="submit"
            disabled={loading || !commodityType}
            className="sm:col-span-2 rounded bg-zinc-900 px-4 py-2 font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {loading ? "Mencari rute..." : "Cari Rute"}
          </button>
        </form>

        {error && (
          <div className="mt-4 rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-6 space-y-6">
            <FinalRecommendation
              route={result.recommended_route}
              rankingPreference={resultRanking}
              scenario={scenarioResult}
            />

            <RouteComparison
              routes={allRoutes}
              recommendedRouteId={result.recommended_route.route_id}
              rankingPreference={resultRanking}
              selectedRouteId={selectedRouteId}
              onSelectRoute={setSelectedRouteId}
            />

            <div>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Rute Direkomendasikan{" "}
                <span className="font-normal normal-case tracking-normal">
                  ({resultRanking === "risiko" ? "risiko terendah" : "tercepat"})
                </span>
              </h2>
              <div
                onClick={() => setSelectedRouteId(result.recommended_route.route_id)}
                className={`cursor-pointer rounded-lg border-2 bg-white p-5 transition-colors dark:bg-zinc-900 ${
                  selectedRouteId === result.recommended_route.route_id
                    ? "border-sky-500 ring-2 ring-sky-200 dark:border-sky-500 dark:ring-sky-900"
                    : "border-emerald-400 dark:border-emerald-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-lg font-semibold">
                    {MODE_LABELS[result.recommended_route.transport_mode] ?? result.recommended_route.transport_mode}
                  </span>
                  <RiskBadge level={result.recommended_route.risk_level} />
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-zinc-600 sm:grid-cols-3 dark:text-zinc-400">
                  <div>Jarak: {result.recommended_route.distance_km.toFixed(0)} km</div>
                  <div>Estimasi: {result.recommended_route.estimated_duration_hours.toFixed(1)} jam</div>
                  <div>Tiba: {formatArrival(result.recommended_route.estimated_arrival)}</div>
                  <div>Risiko: {(result.recommended_route.risk_probability * 100).toFixed(0)}%</div>
                  <div>Confidence: {(result.recommended_route.confidence_score * 100).toFixed(0)}%</div>
                </div>
                {result.recommended_route.trigger_reason && (
                  <div className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                    Peringatan: {result.recommended_route.trigger_reason}
                  </div>
                )}
                <RiskExplanation
                  summary={result.recommended_route.risk_explanation_summary}
                  factors={result.recommended_route.risk_explanation_factors}
                />
                <CargoTempChart route={result.recommended_route} />
                <ProductQualitySummary route={result.recommended_route} />
              </div>
              <AIExplainPanel
                key={`${result.shipment_id}:${result.recommended_route.route_id}`}
                context={buildRouteExplainContext(
                  result.shipment_id,
                  resultRequest?.commodity_type ?? commodityType,
                  result.recommended_route,
                )}
              />
            </div>

            {result.alternative_routes.length > 0 && (
              <div>
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Rute Alternatif
                </h2>
                <div className="space-y-3">
                  {result.alternative_routes.map((alt) => (
                    <AlternativeRouteCard
                      key={alt.route_id}
                      candidate={alt}
                      selected={selectedRouteId === alt.route_id}
                      onSelect={() => setSelectedRouteId(alt.route_id)}
                    />
                  ))}
                </div>
              </div>
            )}

            {resultRequest && (
              <ScenarioSimulator
                key={result.shipment_id}
                baseline={resultRequest}
                onResult={setScenarioResult}
              />
            )}

            <ParameterLegend />
          </div>
        )}
      </div>
    </div>
  );
}
