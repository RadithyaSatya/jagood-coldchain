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

function formatDuration(ms: number): string {
  const totalMinutes = Math.max(0, Math.round(ms / 60000));
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} menit`;
  if (minutes === 0) return `${hours} jam`;
  return `${hours} jam ${minutes} menit`;
}

export default function CheckpointPanel({
  shipmentId,
  routeId,
  estimatedDurationHours,
}: {
  shipmentId: string;
  routeId: string;
  estimatedDurationHours: number;
}) {
  const [routeConfirmed, setRouteConfirmed] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [checkingIn, setCheckingIn] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [finished, setFinished] = useState(false);
  const [label, setLabel] = useState("");
  const [checkpoints, setCheckpoints] = useState<CheckpointReport[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [reportingOutcome, setReportingOutcome] = useState(false);
  const [outcomeReported, setOutcomeReported] = useState(false);
  const [reportedDelayHours, setReportedDelayHours] = useState<number | null>(null);

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

  async function submitCheckpoint(checkpointLabel: string): Promise<CheckpointReport> {
    const position = await getBrowserLocation();
    const point: CheckpointReport = {
      lat: position.coords.latitude,
      lon: position.coords.longitude,
      recorded_at: new Date().toISOString(),
      checkpoint_label: checkpointLabel || undefined,
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
    return point;
  }

  async function handleCheckIn() {
    setCheckingIn(true);
    setError(null);
    try {
      const defaultLabel = checkpoints.length === 0 ? "Mulai" : "";
      const point = await submitCheckpoint(label.trim() || defaultLabel);
      setCheckpoints((prev) => [...prev, point]);
      setLabel("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tidak bisa mengambil lokasi untuk check-in.");
    } finally {
      setCheckingIn(false);
    }
  }

  async function reportOutcome(allPoints: CheckpointReport[]) {
    const actualDurationHours =
      (new Date(allPoints[allPoints.length - 1].recorded_at).getTime() -
        new Date(allPoints[0].recorded_at).getTime()) /
      3_600_000;
    const actualDelayHours = Math.max(0, actualDurationHours - estimatedDurationHours);

    setReportingOutcome(true);
    try {
      const res = await fetch(`${API_BASE}/shipments/${shipmentId}/outcome`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actual_delay_hours: actualDelayHours,
          actual_damage_occurred: false,
          outcome_notes: `Dilaporkan otomatis dari checkpoint tracking (${allPoints.length} titik check-in).`,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Lapor hasil perjalanan gagal (HTTP ${res.status})`);
      }
      setOutcomeReported(true);
      setReportedDelayHours(actualDelayHours);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Check-in selesai, tapi gagal melapor hasil perjalanan otomatis: ${err.message}`
          : "Check-in selesai, tapi gagal melapor hasil perjalanan otomatis.",
      );
    } finally {
      setReportingOutcome(false);
    }
  }

  async function handleFinish() {
    setFinishing(true);
    setError(null);
    try {
      const point = await submitCheckpoint("Selesai");
      const allPoints = [...checkpoints, point];
      setCheckpoints(allPoints);
      setFinished(true);
      await reportOutcome(allPoints);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tidak bisa mengambil lokasi untuk menandai selesai.");
    } finally {
      setFinishing(false);
    }
  }

  const recap =
    finished && checkpoints.length >= 2
      ? {
          startedAt: checkpoints[0].recorded_at,
          finishedAt: checkpoints[checkpoints.length - 1].recorded_at,
          totalMs:
            new Date(checkpoints[checkpoints.length - 1].recorded_at).getTime() -
            new Date(checkpoints[0].recorded_at).getTime(),
        }
      : null;

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
            {finished
              ? "Perjalanan sudah ditandai selesai. Rekap waktu di bawah dipakai untuk mempelajari dampak cuaca nyata terhadap keterlambatan."
              : "Rute dikonfirmasi. Check-in pertama otomatis ditandai \"Mulai\". Tekan \"Check-in\" saat istirahat, lalu \"Tandai Selesai\" saat tiba."}
          </p>
          {!finished && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Label (opsional): rest area, dst."
                className="rounded border border-zinc-300 bg-white px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
              />
              <button
                type="button"
                onClick={handleCheckIn}
                disabled={checkingIn || finishing}
                className="rounded bg-sky-700 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-sky-600 disabled:opacity-50"
              >
                {checkingIn ? "Mengambil lokasi..." : "Check-in di sini"}
              </button>
              <button
                type="button"
                onClick={handleFinish}
                disabled={checkingIn || finishing || checkpoints.length === 0}
                className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-emerald-600 disabled:opacity-50"
              >
                {finishing ? "Mengambil lokasi..." : "Tandai Selesai"}
              </button>
            </div>
          )}
          {checkpoints.length > 0 && (
            <ul className="mt-1 space-y-0.5 text-xs text-zinc-600 dark:text-zinc-400">
              {checkpoints.map((cp, i) => {
                const elapsedMs = new Date(cp.recorded_at).getTime() - new Date(checkpoints[0].recorded_at).getTime();
                return (
                  <li key={i}>
                    {i + 1}. {cp.checkpoint_label || "check-in"} -- {new Date(cp.recorded_at).toLocaleTimeString("id-ID")}
                    {i > 0 && ` (+${formatDuration(elapsedMs)} sejak mulai)`}
                  </li>
                );
              })}
            </ul>
          )}
          {recap && (
            <div className="mt-2 rounded border border-emerald-300 bg-emerald-50 p-2 text-xs text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
              <p className="font-semibold">Rekap waktu perjalanan</p>
              <p>
                Mulai: {new Date(recap.startedAt).toLocaleString("id-ID")}
                <br />
                Selesai: {new Date(recap.finishedAt).toLocaleString("id-ID")}
                <br />
                Total durasi: <strong>{formatDuration(recap.totalMs)}</strong> ({checkpoints.length} titik check-in)
              </p>
              <p className="mt-1.5 border-t border-emerald-300 pt-1.5 dark:border-emerald-800">
                {reportingOutcome && "Melaporkan hasil perjalanan..."}
                {!reportingOutcome && outcomeReported && reportedDelayHours !== null && (
                  <>
                    Hasil perjalanan terlapor -- keterlambatan tercatat{" "}
                    <strong>{formatDuration(reportedDelayHours * 3_600_000)}</strong> dibanding estimasi rute (
                    {estimatedDurationHours.toFixed(1)} jam). Data ini dipakai untuk mempelajari dampak cuaca
                    nyata terhadap keterlambatan darat.
                  </>
                )}
              </p>
            </div>
          )}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}
