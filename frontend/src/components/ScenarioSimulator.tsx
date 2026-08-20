"use client";

import { useState } from "react";
import AIExplainPanel from "@/components/AIExplainPanel";
import CargoTempChart from "@/components/CargoTempChart";
import RiskBadge from "@/components/RiskBadge";
import RiskExplanation from "@/components/RiskExplanation";
import { buildScenarioExplainContext } from "@/lib/aiExplain";
import type {
  ColdChainEquipment,
  InsulationQuality,
  RouteCandidate,
  RouteRequestPayload,
  ScenarioResponse,
  TransportModePreference,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const FACTOR_LABELS: Record<string, string> = {
  expected_delay_hours: "Keterlambatan tambahan",
  transport_mode: "Moda transportasi",
  cold_chain_equipment: "Peralatan cold chain",
  insulation_quality: "Kualitas insulasi",
  max_cargo_temp_excess_c: "Paparan suhu di atas batas ideal",
  distance_km: "Jarak rute",
  wave_height_m: "Tinggi gelombang",
  weather_condition: "Kondisi cuaca",
};

function formatFactorValue(factor: string, value: number | string): string {
  if (typeof value !== "number") return value;
  if (factor.endsWith("_hours")) return `${value.toFixed(1)} jam`;
  if (factor.endsWith("_km")) return `${value.toFixed(1)} km`;
  if (factor.endsWith("_c")) return `${value.toFixed(1)}°C`;
  if (factor === "wave_height_m") return `${value.toFixed(2)} m`;
  return value.toFixed(2);
}

function ScenarioRouteCard({ title, route }: { title: string; route: RouteCandidate }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold">{title}</h3>
        <RiskBadge level={route.risk_level} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-sm text-zinc-600 dark:text-zinc-400">
        <div>
          <dt className="text-xs uppercase tracking-wide">Skor risiko</dt>
          <dd className="font-semibold text-zinc-900 dark:text-zinc-100">
            {(route.risk_probability * 100).toFixed(2)}%
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide">Delay tambahan</dt>
          <dd className="font-semibold text-zinc-900 dark:text-zinc-100">
            {route.expected_delay_hours.toFixed(1)} jam
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide">Moda</dt>
          <dd>{route.transport_mode}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide">Cold chain</dt>
          <dd>{route.cold_chain_equipment}</dd>
        </div>
      </dl>
      <RiskExplanation summary={route.risk_explanation_summary} factors={route.risk_explanation_factors} />
      <CargoTempChart route={route} />
    </div>
  );
}

export default function ScenarioSimulator({ baseline }: { baseline: RouteRequestPayload }) {
  const [delayHours, setDelayHours] = useState(12);
  const [transportMode, setTransportMode] = useState<"" | TransportModePreference>("");
  const [equipment, setEquipment] = useState<"" | ColdChainEquipment>(
    baseline.cold_chain_equipment === "reefer" ? "pasif" : "reefer",
  );
  const [insulation, setInsulation] = useState<InsulationQuality>("buruk");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScenarioResponse | null>(null);

  const effectiveEquipment = equipment || baseline.cold_chain_equipment;

  async function handleSimulate(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const changes: Record<string, string | number> = { delay_hours: delayHours };
    if (transportMode) changes.transport_mode = transportMode;
    if (equipment) changes.cold_chain_equipment = equipment;
    if (effectiveEquipment === "pasif") changes.insulation_quality = insulation;

    try {
      const response = await fetch(`${API_BASE}/simulate-scenario`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseline, changes }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail ?? `Simulasi gagal (HTTP ${response.status})`);
      }
      setResult((await response.json()) as ScenarioResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulasi gagal karena kesalahan tak terduga.");
    } finally {
      setLoading(false);
    }
  }

  const deltaPoints = result ? result.risk_delta * 100 : 0;
  const deltaLabel = `${deltaPoints > 0 ? "+" : ""}${deltaPoints.toFixed(2)} poin`;

  return (
    <section className="scenario-panel">
      <p className="eyebrow">Analisis dampak</p>
      <h2>Simulasi Skenario</h2>
      <p className="mt-1 text-sm text-slate-600">
        Uji dampak gangguan terhadap rute ini. Baseline dan skenario dinilai ulang oleh model risiko yang sama.
      </p>

      <form onSubmit={handleSimulate} className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="form-field">
          Delay tambahan (jam)
          <input
            type="number"
            min={0}
            max={168}
            step={1}
            value={delayHours}
            disabled={loading}
            onChange={(e) => setDelayHours(Number(e.target.value))}
            className="form-control"
          />
        </label>

        <label className="form-field">
          Ubah moda
          <select
            value={transportMode}
            disabled={loading}
            onChange={(e) => setTransportMode(e.target.value as "" | TransportModePreference)}
            className="form-control"
          >
            <option value="">Tetap seperti baseline</option>
            <option value="darat">Darat</option>
            <option value="laut">Laut</option>
            <option value="kombinasi">Kombinasi</option>
            <option value="semua">Pilih terbaik dari semua</option>
          </select>
        </label>

        <label className="form-field">
          Ubah cold chain
          <select
            value={equipment}
            disabled={loading}
            onChange={(e) => setEquipment(e.target.value as "" | ColdChainEquipment)}
            className="form-control"
          >
            <option value="">Tetap seperti baseline</option>
            <option value="reefer">Reefer aktif</option>
            <option value="pasif">Pendingin pasif</option>
          </select>
        </label>

        {effectiveEquipment === "pasif" && (
          <label className="form-field">
            Kualitas insulasi
            <select
              value={insulation}
              disabled={loading}
              onChange={(e) => setInsulation(e.target.value as InsulationQuality)}
              className="form-control"
            >
              <option value="baik">Baik</option>
              <option value="sedang">Sedang</option>
              <option value="buruk">Buruk</option>
            </select>
          </label>
        )}

        <button
          type="submit"
          disabled={loading || delayHours < 0 || delayHours > 168}
          className="primary-action sm:col-span-2 lg:col-span-4"
        >
          {loading ? "Menghitung skenario..." : "Jalankan Simulasi"}
        </button>
      </form>

      {loading && (
        <div className="operation-loading" role="status" aria-live="polite">
          <span className="loading-spinner" aria-hidden />
          <div>
            <strong>Menjalankan simulasi</strong>
            <span>Membandingkan kondisi skenario dengan baseline.</span>
          </div>
        </div>
      )}

      {error && (
        <div className="app-alert mt-4" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ScenarioRouteCard title="Baseline" route={result.baseline} />
            <ScenarioRouteCard title="Setelah Gangguan" route={result.simulated} />
          </div>

          <div className="ui-card">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium">Perubahan risiko</span>
              <span
                className={`text-lg font-bold ${
                  deltaPoints > 0
                    ? "text-red-600 dark:text-red-400"
                    : deltaPoints < 0
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-zinc-600 dark:text-zinc-400"
                }`}
              >
                {deltaLabel}
              </span>
            </div>
            <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{result.recommendation}</p>

            {result.affected_factors.length > 0 && (
              <div className="mt-4">
                <h3 className="text-sm font-semibold">Faktor yang berubah</h3>
                <ul className="mt-2 space-y-1 text-sm text-zinc-600 dark:text-zinc-400">
                  {result.affected_factors.map((factor) => (
                    <li key={factor.factor}>
                      {FACTOR_LABELS[factor.factor] ?? factor.factor}: {formatFactorValue(factor.factor, factor.baseline_value)} →{" "}
                      {formatFactorValue(factor.factor, factor.simulated_value)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <AIExplainPanel
            context={buildScenarioExplainContext(
              baseline.shipment_id ?? result.scenario_id,
              baseline.commodity_type,
              result,
            )}
          />
        </div>
      )}
    </section>
  );
}
