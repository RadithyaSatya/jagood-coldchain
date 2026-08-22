"use client";

import { useState } from "react";
import AIExplainPanel from "@/components/AIExplainPanel";
import CargoTempChart from "@/components/CargoTempChart";
import ProductQualitySummary from "@/components/ProductQualitySummary";
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
      <ProductQualitySummary route={route} />
    </div>
  );
}

export default function ScenarioSimulator({
  baseline,
  onResult,
}: {
  baseline: RouteRequestPayload;
  onResult?: (result: ScenarioResponse | null) => void;
}) {
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
    onResult?.(null);

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
      const scenario = (await response.json()) as ScenarioResponse;
      setResult(scenario);
      onResult?.(scenario);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulasi gagal karena kesalahan tak terduga.");
    } finally {
      setLoading(false);
    }
  }

  const deltaPoints = result ? result.risk_delta * 100 : 0;
  const deltaLabel = `${deltaPoints > 0 ? "+" : ""}${deltaPoints.toFixed(2)} poin`;

  return (
    <section className="rounded-lg border border-violet-200 bg-violet-50 p-5 dark:border-violet-900 dark:bg-violet-950/30">
      <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Scenario Simulator</h2>
      <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
        Uji dampak gangguan terhadap rute ini. Baseline dan skenario dinilai ulang oleh model risiko yang sama.
      </p>

      <form onSubmit={handleSimulate} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col gap-1 text-sm">
          Delay tambahan (jam)
          <input
            type="number"
            min={0}
            max={168}
            step={1}
            value={delayHours}
            onChange={(e) => setDelayHours(Number(e.target.value))}
            className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Ubah moda
          <select
            value={transportMode}
            onChange={(e) => setTransportMode(e.target.value as "" | TransportModePreference)}
            className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">Tetap seperti baseline</option>
            <option value="darat">Darat</option>
            <option value="laut">Laut</option>
            <option value="kombinasi">Kombinasi</option>
            <option value="semua">Pilih terbaik dari semua</option>
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Ubah cold chain
          <select
            value={equipment}
            onChange={(e) => setEquipment(e.target.value as "" | ColdChainEquipment)}
            className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">Tetap seperti baseline</option>
            <option value="reefer">Reefer aktif</option>
            <option value="pasif">Pendingin pasif</option>
          </select>
        </label>

        {effectiveEquipment === "pasif" && (
          <label className="flex flex-col gap-1 text-sm">
            Kualitas insulasi
            <select
              value={insulation}
              onChange={(e) => setInsulation(e.target.value as InsulationQuality)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-900"
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
          className="rounded bg-violet-700 px-4 py-2 font-medium text-white transition-colors hover:bg-violet-600 disabled:opacity-50 sm:col-span-2 lg:col-span-4"
        >
          {loading ? "Menghitung skenario..." : "Jalankan Simulasi"}
        </button>
      </form>

      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            <ScenarioRouteCard title="Baseline" route={result.baseline} />
            <ScenarioRouteCard title="Setelah Gangguan" route={result.simulated} />
          </div>

          <div className="rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
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
            key={result.scenario_id}
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
