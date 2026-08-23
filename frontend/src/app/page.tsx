"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import AIExplainPanel from "@/components/AIExplainPanel";
import AppHeader from "@/components/AppHeader";
import CargoTempChart from "@/components/CargoTempChart";
import CheckpointPanel from "@/components/CheckpointPanel";
import ParameterLegend from "@/components/ParameterLegend";
import RiskBadge from "@/components/RiskBadge";
import QualityBadge from "@/components/QualityBadge";
import RiskExplanation from "@/components/RiskExplanation";
import SearchSelect from "@/components/SearchSelect";
import ScenarioSimulator from "@/components/ScenarioSimulator";
import { buildRouteExplainContext } from "@/lib/aiExplain";
import { CITIES } from "@/lib/cities";
import { environmentalDataLabel } from "@/lib/dataProvenance";
import type {
  City,
  ColdChainEquipment,
  Commodity,
  FinalRecommendationResponse,
  InsulationQuality,
  PredictRouteResponse,
  RankingPreference,
  RouteCandidate,
  RouteRequestPayload,
  TransportModePreference,
} from "@/lib/types";

function ForecastMapLoading() {
  return (
    <div className="map-loading-state" role="status" aria-live="polite">
      <div className="map-loading-state__wave" aria-hidden />
      <div>
        <strong>Memuat peta prakiraan</strong>
        <span>Menyiapkan titik pengiriman dan layer rute.</span>
      </div>
    </div>
  );
}

function RouteSearchLoading() {
  return (
    <div className="operation-loading" role="status" aria-live="polite">
      <span className="loading-spinner" aria-hidden />
      <div>
        <strong>Mencari rute terbaik</strong>
        <span>Menilai risiko, kondisi perjalanan, dan alternatif rute.</span>
      </div>
    </div>
  );
}

const RouteMap = dynamic(() => import("@/components/RouteMap"), {
  ssr: false,
  loading: () => null,
});

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const MODE_LABELS: Record<string, string> = {
  darat: "Darat",
  laut: "Laut",
  kombinasi: "Kombinasi (Darat + Laut)",
};

const CITY_OPTIONS = CITIES.map((city) => ({ value: city.label, label: city.label }));
const TRANSPORT_OPTIONS = [
  { value: "semua", label: "Semua moda" },
  { value: "darat", label: "Darat saja" },
  { value: "laut", label: "Laut saja" },
  { value: "kombinasi", label: "Kombinasi" },
];
const RANKING_OPTIONS = [
  { value: "risiko", label: "Risiko kerusakan terendah" },
  { value: "kecepatan", label: "Waktu tempuh tercepat" },
];
const EQUIPMENT_OPTIONS = [
  { value: "reefer", label: "Reefer (pendingin aktif)" },
  { value: "pasif", label: "Pasif (tanpa pendingin aktif)" },
];
const INSULATION_OPTIONS = [
  { value: "baik", label: "Baik (cooler box tebal)" },
  { value: "sedang", label: "Sedang (styrofoam standar)" },
  { value: "buruk", label: "Buruk (kardus/insulasi tipis)" },
];

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
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`result-card w-full cursor-pointer p-4 text-left ${
        selected
          ? "result-card--selected"
          : ""
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold">{MODE_LABELS[candidate.transport_mode] ?? candidate.transport_mode}</span>
        <div className="flex items-center gap-1.5">
          <RiskBadge level={candidate.risk_level} />
          <QualityBadge status={candidate.quality_status} />
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-slate-600 sm:grid-cols-3">
        <div>Jarak: {candidate.distance_km.toFixed(0)} km</div>
        <div>Estimasi: {candidate.estimated_duration_hours.toFixed(1)} jam</div>
        <div>Tiba: {formatArrival(candidate.estimated_arrival)}</div>
        <div>Skor: {(candidate.risk_probability * 100).toFixed(0)}%</div>
        <div>Routing: {candidate.data_quality === "estimated" ? "Fallback estimasi" : "Tanpa fallback"}</div>
        <div>Lingkungan: {environmentalDataLabel(candidate)}</div>
        <div>
          Sisa umur simpan: {candidate.remaining_shelf_life_hours.toFixed(1)} jam ({candidate.remaining_shelf_life_pct.toFixed(0)}%)
        </div>
      </div>
      <RiskExplanation summary={candidate.risk_explanation_summary} factors={candidate.risk_explanation_factors} />
      <CargoTempChart route={candidate} />
    </button>
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
  const [commoditiesLoading, setCommoditiesLoading] = useState(true);
  const [mapLoading, setMapLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictRouteResponse | null>(null);
  const [resultRequest, setResultRequest] = useState<RouteRequestPayload | null>(null);
  // The preference the displayed result was actually produced with -- kept
  // separate from rankingPreference so changing the selector without
  // re-submitting can't mislabel how the listed routes were ordered.
  const [resultRanking, setResultRanking] = useState<"risiko" | "kecepatan">("risiko");
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/commodities`)
      .then((res) => res.json())
      .then((data: Commodity[]) => {
        setCommodities(data);
        if (data.length > 0) setCommodityType(data[0].commodity_type);
      })
      .catch(() => setError("Tidak bisa memuat daftar komoditas dari backend."))
      .finally(() => setCommoditiesLoading(false));
  }, []);

  function handleOriginChange(lat: number, lon: number) {
    setOrigin({ label: formatCoord(lat, lon), lat, lon });
  }
  function handleDestinationChange(lat: number, lon: number) {
    setDestination({ label: formatCoord(lat, lon), lat, lon });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setResultRequest(null);

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
      const res = await fetch("/api/final-recommendation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shipment: requestPayload }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Request gagal (HTTP ${res.status})`);
      }

      const finalResult = (await res.json()) as FinalRecommendationResponse;
      const data: PredictRouteResponse = finalResult.route_plan;
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
  const selectedRoute = allRoutes.find((route) => route.route_id === selectedRouteId) ?? result?.recommended_route;
  const initialLoading = commoditiesLoading || mapLoading;
  const formBusy = initialLoading || loading;

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <AppHeader />
      <main className="planner-page">
        <div className="planner-container">
          <section className="planner-hero" aria-labelledby="page-title">
            <p className="eyebrow">JaGOOD Cold Chain</p>
            <h1 id="page-title">Rencanakan pengiriman dengan risiko yang terukur.</h1>
            <p>
              Bandingkan rute berdasarkan risiko kerusakan produk, waktu tempuh, dan kondisi cold chain sebelum
              pengiriman dimulai.
            </p>
          </section>

          <section id="planner" className="planner-workspace" aria-labelledby="planner-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Perencanaan rute</p>
                <h2 id="planner-title">Tentukan titik dan detail pengiriman</h2>
              </div>
            </div>

            <div className="map-controls" aria-label="Kontrol pemilihan titik peta">
              <button
                type="button"
                disabled={formBusy}
                onClick={() => setPickMode("origin")}
                className={`map-point-button ${pickMode === "origin" ? "map-point-button--active" : ""}`}
              >
                Pilih titik asal di peta
              </button>
              <button
                type="button"
                disabled={formBusy}
                onClick={() => setPickMode("destination")}
                className={`map-point-button ${pickMode === "destination" ? "map-point-button--active" : ""}`}
              >
                Pilih titik tujuan di peta
              </button>
              <span className="map-controls__hint">Klik peta atau seret penanda A/B untuk memperbarui titik.</span>
            </div>

            <div className="planner-map" aria-busy={mapLoading}>
              <RouteMap
                origin={origin}
                destination={destination}
                onOriginChange={handleOriginChange}
                onDestinationChange={handleDestinationChange}
                pickMode={formBusy ? null : pickMode}
                routes={allRoutes}
                recommendedRouteId={result?.recommended_route.route_id}
                selectedRouteId={selectedRouteId ?? undefined}
                onSelectRoute={setSelectedRouteId}
                onReady={() => setMapLoading(false)}
              />
              {mapLoading && <ForecastMapLoading />}
              <div className="map-forecast-overlay">
                <ParameterLegend route={selectedRoute} />
              </div>
            </div>

            <form onSubmit={handleSubmit} className="planner-form" aria-busy={formBusy}>
              <div className="form-field">
                Asal
                <SearchSelect
                  label="titik asal"
                  value={origin.label}
                  options={CITY_OPTIONS}
                  placeholder="Pilih titik asal"
                  disabled={formBusy}
                  onValueChange={(label) => setOrigin(CITIES.find((city) => city.label === label) ?? origin)}
                />
              </div>

              <div className="form-field">
                Tujuan
                <SearchSelect
                  label="titik tujuan"
                  value={destination.label}
                  options={CITY_OPTIONS}
                  placeholder="Pilih titik tujuan"
                  disabled={formBusy}
                  onValueChange={(label) => setDestination(CITIES.find((city) => city.label === label) ?? destination)}
                />
              </div>

              <div className="form-field">
                Jenis Komoditas
                <SearchSelect
                  label="jenis komoditas"
                  value={commodityType}
                  options={commodities.map((commodity) => ({ value: commodity.commodity_type, label: commodity.commodity_type }))}
                  placeholder="Pilih komoditas"
                  disabled={formBusy}
                  onValueChange={setCommodityType}
                />
              </div>

              <label className="form-field">
                Waktu Keberangkatan
                <input
                  type="datetime-local"
                  value={departureTime}
                  disabled={formBusy}
                  onChange={(e) => setDepartureTime(e.target.value)}
                  className="form-control"
                />
              </label>

              <div className="form-field">
                Preferensi Moda Transportasi
                <SearchSelect
                  label="moda transportasi"
                  value={transportModePreference}
                  options={TRANSPORT_OPTIONS}
                  placeholder="Pilih moda"
                  disabled={formBusy}
                  onValueChange={(value) => setTransportModePreference(value as TransportModePreference)}
                />
              </div>

              <div className="form-field">
                Urutkan Rute Berdasarkan
                <SearchSelect
                  label="preferensi urutan"
                  value={rankingPreference}
                  options={RANKING_OPTIONS}
                  placeholder="Pilih urutan"
                  disabled={formBusy}
                  onValueChange={(value) => setRankingPreference(value as RankingPreference)}
                />
              </div>

              <div className="form-field">
                Peralatan Cold Chain
                <SearchSelect
                  label="peralatan cold chain"
                  value={coldChainEquipment}
                  options={EQUIPMENT_OPTIONS}
                  placeholder="Pilih peralatan"
                  disabled={formBusy}
                  onValueChange={(value) => setColdChainEquipment(value as ColdChainEquipment)}
                />
              </div>

              {coldChainEquipment === "pasif" && (
                <div className="form-field sm:col-span-2">
                  Kualitas Insulasi Kemasan
                  <SearchSelect
                    label="kualitas insulasi"
                    value={insulationQuality}
                    options={INSULATION_OPTIONS}
                    placeholder="Pilih kualitas insulasi"
                    disabled={formBusy}
                    onValueChange={(value) => setInsulationQuality(value as InsulationQuality)}
                  />
                </div>
              )}

              <button type="submit" disabled={loading || initialLoading || !commodityType} className="primary-action sm:col-span-2">
                {loading ? "Mencari rute..." : initialLoading ? "Menyiapkan prakiraan..." : "Cari Rute"}
              </button>
            </form>
            {loading && <RouteSearchLoading />}
          </section>

        {error && (
          <div className="app-alert mt-6" role="alert">
            {error}
          </div>
        )}

        {result && (
          <section id="hasil-rute" className="results-section" aria-label="Hasil perencanaan rute">
            <div>
              <h2 className="result-section-title">
                Rute Direkomendasikan{" "}
                <span className="font-normal normal-case tracking-normal">
                  ({resultRanking === "risiko" ? "risiko terendah" : "tercepat"})
                </span>
              </h2>
              <button
                type="button"
                onClick={() => setSelectedRouteId(result.recommended_route.route_id)}
                aria-pressed={selectedRouteId === result.recommended_route.route_id}
                className={`result-card result-card--recommended w-full cursor-pointer p-6 text-left ${
                  selectedRouteId === result.recommended_route.route_id
                    ? "result-card--selected"
                    : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-lg font-semibold">
                    {MODE_LABELS[result.recommended_route.transport_mode] ?? result.recommended_route.transport_mode}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <RiskBadge level={result.recommended_route.risk_level} />
                    <QualityBadge status={result.recommended_route.quality_status} />
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm text-slate-600 sm:grid-cols-3">
                  <div>Jarak: {result.recommended_route.distance_km.toFixed(0)} km</div>
                  <div>Estimasi: {result.recommended_route.estimated_duration_hours.toFixed(1)} jam</div>
                  <div>Tiba: {formatArrival(result.recommended_route.estimated_arrival)}</div>
                  <div>Risiko: {(result.recommended_route.risk_probability * 100).toFixed(0)}%</div>
                  <div>Confidence: {(result.recommended_route.confidence_score * 100).toFixed(0)}%</div>
                  <div>
                    Sisa umur simpan: {result.recommended_route.remaining_shelf_life_hours.toFixed(1)} jam (
                    {result.recommended_route.remaining_shelf_life_pct.toFixed(0)}%)
                  </div>
                </div>
                {result.recommended_route.trigger_reason && (
                  <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    Peringatan: {result.recommended_route.trigger_reason}
                  </div>
                )}
                <RiskExplanation
                  summary={result.recommended_route.risk_explanation_summary}
                  factors={result.recommended_route.risk_explanation_factors}
                />
                <CargoTempChart route={result.recommended_route} />
              </button>
              <AIExplainPanel
                context={buildRouteExplainContext(
                  result.shipment_id,
                  resultRequest?.commodity_type ?? commodityType,
                  result.recommended_route,
                )}
              />
            </div>

            {result.alternative_routes.length > 0 && (
              <div>
                <h2 className="result-section-title">
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

            {selectedRouteId && (
              <div>
                <h2 className="result-section-title">Lacak Perjalanan Rute Terpilih</h2>
                <CheckpointPanel
                  key={`${result.shipment_id}-${selectedRouteId}`}
                  shipmentId={result.shipment_id}
                  routeId={selectedRouteId}
                />
              </div>
            )}

            <div id="simulasi">
              {resultRequest && <ScenarioSimulator key={result.shipment_id} baseline={resultRequest} />}
            </div>
          </section>
        )}
        </div>
      </main>
    </div>
  );
}
