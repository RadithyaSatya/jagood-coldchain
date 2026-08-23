"use client";

import { useState } from "react";
import type { CheckpointReport } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

function getBrowserLocation(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("Browser ini tidak mendukung lokasi."));
      return;
    }
    navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 15000 });
  });
}

export default function CheckpointPanel({ shipmentId, routeId }: { shipmentId: string; routeId: string }) {
  const [routeConfirmed, setRouteConfirmed] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);
  const [label, setLabel] = useState("");
  const [checkpoints, setCheckpoints] = useState<CheckpointReport[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirmRoute() {
    setConfirming(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/shipments/${shipmentId}/select-route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ route_id: routeId }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Konfirmasi rute gagal (HTTP ${res.status})`);
      }
      setRouteConfirmed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Konfirmasi rute gagal karena kesalahan tak terduga.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleCheckIn() {
    setCheckingIn(true);
    setError(null);
    try {
      const position = await getBrowserLocation();
      const point: CheckpointReport = {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
        recorded_at: new Date().toISOString(),
        checkpoint_label: label.trim() || undefined,
      };
      const res = await fetch(`${API_BASE}/shipments/${shipmentId}/checkpoints`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ points: [point] }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Check-in gagal (HTTP ${res.status})`);
      }
      setCheckpoints((prev) => [...prev, point]);
      setLabel("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tidak bisa mengambil lokasi untuk check-in.");
    } finally {
      setCheckingIn(false);
    }
  }

  return (
    <div className="mt-3 rounded-lg border border-dashed border-zinc-300 p-3 text-sm dark:border-zinc-700">
      {!routeConfirmed ? (
        <button
          type="button"
          onClick={handleConfirmRoute}
          disabled={confirming}
          className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
        >
          {confirming ? "Mengonfirmasi..." : "Konfirmasi rute ini & mulai lacak perjalanan"}
        </button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Rute dikonfirmasi. Tekan &quot;Check-in&quot; di titik keberangkatan, saat istirahat, dan saat tiba --
            dipakai untuk mempelajari dampak cuaca nyata terhadap keterlambatan.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Label (opsional): rest area, tiba, dst."
              className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
            />
            <button
              type="button"
              onClick={handleCheckIn}
              disabled={checkingIn}
              className="rounded bg-sky-700 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-sky-600 disabled:opacity-50"
            >
              {checkingIn ? "Mengambil lokasi..." : "Check-in di sini"}
            </button>
          </div>
          {checkpoints.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-zinc-600 dark:text-zinc-400">
              {checkpoints.map((cp, i) => (
                <li key={i}>
                  {i + 1}. {cp.checkpoint_label || "check-in"} -- {new Date(cp.recorded_at).toLocaleTimeString("id-ID")}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
