"use client";

import { useEffect, useState } from "react";
import RiskBadge from "@/components/RiskBadge";
import { CITIES } from "@/lib/cities";
import type { Commodity, PredictRouteResponse, RouteCandidate } from "@/lib/types";

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

function RouteRow({ candidate }: { candidate: RouteCandidate }) {
  return (
    <tr className="border-t border-zinc-200 dark:border-zinc-800">
      <td className="py-2 pl-4 pr-4 font-medium">{MODE_LABELS[candidate.transport_mode] ?? candidate.transport_mode}</td>
      <td className="py-2 pr-4">{candidate.distance_km.toFixed(0)} km</td>
      <td className="py-2 pr-4">{candidate.estimated_duration_hours.toFixed(1)} jam</td>
      <td className="py-2 pr-4">
        <RiskBadge level={candidate.risk_level} />
      </td>
      <td className="py-2 pr-4 text-zinc-500 dark:text-zinc-400">
        {(candidate.risk_probability * 100).toFixed(0)}%
      </td>
      <td className="py-2 pr-4 text-zinc-500 dark:text-zinc-400">
        {candidate.data_quality === "estimated" ? "Estimasi" : "Live"}
      </td>
    </tr>
  );
}

export default function Home() {
  const [commodities, setCommodities] = useState<Commodity[]>([]);
  const [originIdx, setOriginIdx] = useState(0);
  const [destinationIdx, setDestinationIdx] = useState(1);
  const [commodityType, setCommodityType] = useState("");
  const [departureTime, setDepartureTime] = useState(defaultDepartureTime());
  const [transportModePreference, setTransportModePreference] = useState("semua");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PredictRouteResponse | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/commodities`)
      .then((res) => res.json())
      .then((data: Commodity[]) => {
        setCommodities(data);
        if (data.length > 0) setCommodityType(data[0].commodity_type);
      })
      .catch(() => setError("Tidak bisa memuat daftar komoditas dari backend."));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const origin = CITIES[originIdx];
    const destination = CITIES[destinationIdx];

    try {
      const res = await fetch(`${API_BASE}/predict-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin: { lat: origin.lat, lon: origin.lon },
          destination: { lat: destination.lat, lon: destination.lon },
          commodity_type: commodityType,
          departure_time: new Date(departureTime).toISOString(),
          transport_mode_preference: transportModePreference,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Request gagal (HTTP ${res.status})`);
      }

      setResult(await res.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Terjadi kesalahan tak terduga.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-1 flex-col items-center bg-zinc-50 px-4 py-10 dark:bg-zinc-950">
      <div className="w-full max-w-3xl">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
          JaGOOD Smart Route Planner
        </h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Rekomendasi rute cold chain berbasis prediksi risiko, bukan sekadar jarak/waktu tercepat.
        </p>

        <form
          onSubmit={handleSubmit}
          className="mt-6 grid grid-cols-1 gap-4 rounded-lg border border-zinc-200 bg-white p-5 sm:grid-cols-2 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <label className="flex flex-col gap-1 text-sm">
            Asal
            <select
              value={originIdx}
              onChange={(e) => setOriginIdx(Number(e.target.value))}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              {CITIES.map((city, i) => (
                <option key={city.label} value={i}>
                  {city.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-1 text-sm">
            Tujuan
            <select
              value={destinationIdx}
              onChange={(e) => setDestinationIdx(Number(e.target.value))}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
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

          <label className="flex flex-col gap-1 text-sm sm:col-span-2">
            Preferensi Moda Transportasi
            <select
              value={transportModePreference}
              onChange={(e) => setTransportModePreference(e.target.value)}
              className="rounded border border-zinc-300 bg-white px-2 py-1.5 dark:border-zinc-700 dark:bg-zinc-800"
            >
              <option value="semua">Semua</option>
              <option value="darat">Darat saja</option>
              <option value="laut">Laut saja</option>
              <option value="kombinasi">Kombinasi</option>
            </select>
          </label>

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
            <div>
              <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                Rute Direkomendasikan
              </h2>
              <div className="rounded-lg border-2 border-emerald-400 bg-white p-5 dark:border-emerald-700 dark:bg-zinc-900">
                <div className="flex items-center justify-between">
                  <span className="text-lg font-semibold">
                    {MODE_LABELS[result.recommended_route.transport_mode] ?? result.recommended_route.transport_mode}
                  </span>
                  <RiskBadge level={result.recommended_route.risk_level} />
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-sm text-zinc-600 sm:grid-cols-4 dark:text-zinc-400">
                  <div>Jarak: {result.recommended_route.distance_km.toFixed(0)} km</div>
                  <div>Estimasi: {result.recommended_route.estimated_duration_hours.toFixed(1)} jam</div>
                  <div>Risiko: {(result.recommended_route.risk_probability * 100).toFixed(0)}%</div>
                  <div>Confidence: {(result.recommended_route.confidence_score * 100).toFixed(0)}%</div>
                </div>
                {result.recommended_route.trigger_reason && (
                  <div className="mt-3 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300">
                    Peringatan: {result.recommended_route.trigger_reason}
                  </div>
                )}
              </div>
            </div>

            {result.alternative_routes.length > 0 && (
              <div>
                <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  Rute Alternatif
                </h2>
                <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="text-zinc-500 dark:text-zinc-400">
                        <th className="py-2 pl-4 pr-4 font-medium">Moda</th>
                        <th className="py-2 pr-4 font-medium">Jarak</th>
                        <th className="py-2 pr-4 font-medium">Estimasi</th>
                        <th className="py-2 pr-4 font-medium">Risiko</th>
                        <th className="py-2 pr-4 font-medium">Skor</th>
                        <th className="py-2 pr-4 font-medium">Data</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.alternative_routes.map((alt) => (
                        <RouteRow key={alt.route_id} candidate={alt} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
