"use client";

import { useState } from "react";
import type { CheckpointReport } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";

function getBrowserLocation(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) return reject(new Error("Browser ini tidak mendukung lokasi."));
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

export default function CheckpointPanel({ shipmentId, routeId, routeLabel, estimatedDurationHours }: {
  shipmentId: string;
  routeId: string;
  routeLabel: string;
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
    setConfirming(true); setError(null);
    try {
      const res = await fetch(`${API_BASE}/shipments/${shipmentId}/select-route`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ route_id: routeId }) });
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail ?? `Konfirmasi rute gagal (HTTP ${res.status})`); }
      setRouteConfirmed(true);
    } catch (err) { setError(err instanceof Error ? err.message : "Konfirmasi rute gagal karena kesalahan tak terduga."); }
    finally { setConfirming(false); }
  }

  async function submitCheckpoint(checkpointLabel: string): Promise<CheckpointReport> {
    const position = await getBrowserLocation();
    const point: CheckpointReport = { lat: position.coords.latitude, lon: position.coords.longitude, recorded_at: new Date().toISOString(), checkpoint_label: checkpointLabel || undefined };
    const res = await fetch(`${API_BASE}/shipments/${shipmentId}/checkpoints`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ points: [point] }) });
    if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail ?? `Check-in gagal (HTTP ${res.status})`); }
    return point;
  }

  async function handleCheckIn() {
    setCheckingIn(true); setError(null);
    try { const point = await submitCheckpoint(label.trim() || (checkpoints.length === 0 ? "Mulai" : "")); setCheckpoints((prev) => [...prev, point]); setLabel(""); }
    catch (err) { setError(err instanceof Error ? err.message : "Tidak bisa mengambil lokasi untuk check-in."); }
    finally { setCheckingIn(false); }
  }

  async function reportOutcome(allPoints: CheckpointReport[]) {
    const actualDurationHours = (new Date(allPoints[allPoints.length - 1].recorded_at).getTime() - new Date(allPoints[0].recorded_at).getTime()) / 3_600_000;
    const actualDelayHours = Math.max(0, actualDurationHours - estimatedDurationHours);
    setReportingOutcome(true);
    try {
      const res = await fetch(`${API_BASE}/shipments/${shipmentId}/outcome`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actual_delay_hours: actualDelayHours, actual_damage_occurred: false, outcome_notes: `Dilaporkan otomatis dari checkpoint tracking (${allPoints.length} titik check-in).` }) });
      if (!res.ok) { const body = await res.json().catch(() => ({})); throw new Error(body.detail ?? `Lapor hasil perjalanan gagal (HTTP ${res.status})`); }
      setOutcomeReported(true); setReportedDelayHours(actualDelayHours);
    } catch (err) { setError(err instanceof Error ? `Check-in selesai, tapi gagal melapor hasil perjalanan otomatis: ${err.message}` : "Check-in selesai, tapi gagal melapor hasil perjalanan otomatis."); }
    finally { setReportingOutcome(false); }
  }

  async function handleFinish() {
    setFinishing(true); setError(null);
    try { const point = await submitCheckpoint("Selesai"); const allPoints = [...checkpoints, point]; setCheckpoints(allPoints); setFinished(true); await reportOutcome(allPoints); }
    catch (err) { setError(err instanceof Error ? err.message : "Tidak bisa mengambil lokasi untuk menandai selesai."); }
    finally { setFinishing(false); }
  }

  const recap = finished && checkpoints.length >= 2 ? { startedAt: checkpoints[0].recorded_at, finishedAt: checkpoints[checkpoints.length - 1].recorded_at, totalMs: new Date(checkpoints[checkpoints.length - 1].recorded_at).getTime() - new Date(checkpoints[0].recorded_at).getTime() } : null;
  const status = finished ? "Perjalanan selesai" : routeConfirmed ? "Pelacakan aktif" : "Belum dimulai";

  return (
    <section className="journey-tracker" aria-label="Pelacakan perjalanan rute terpilih">
      <header className="journey-tracker__header">
        <div>
          <p className="eyebrow">Rute terpilih</p>
          <h3>{routeLabel}</h3>
          <p className="journey-tracker__summary">Estimasi perjalanan {estimatedDurationHours.toFixed(1)} jam. Catat lokasi saat mulai, berhenti, atau tiba.</p>
        </div>
        <span className={`journey-tracker__status journey-tracker__status--${finished ? "complete" : routeConfirmed ? "active" : "pending"}`}>{status}</span>
      </header>

      {!routeConfirmed ? (
        <div className="journey-tracker__start">
          <div className="journey-tracker__steps" aria-label="Alur pelacakan">
            <span><b>1</b> Konfirmasi rute</span><span><b>2</b> Catat titik perjalanan</span><span><b>3</b> Tandai selesai</span>
          </div>
          <p>Konfirmasi rute ini untuk mengaktifkan pencatatan lokasi dari perangkat Anda.</p>
          <button type="button" onClick={handleConfirmRoute} disabled={confirming} className="primary-action journey-tracker__action">
            {confirming ? "Mengonfirmasi rute..." : "Konfirmasi & mulai pelacakan"}
          </button>
        </div>
      ) : (
        <div className="journey-tracker__body">
          {!finished && <>
            <p className="journey-tracker__instruction">{checkpoints.length === 0 ? "Tekan “Catat lokasi saat ini” ketika perjalanan dimulai." : "Tambahkan titik baru saat berhenti atau ketika kondisi perjalanan berubah."}</p>
            <div className="journey-tracker__controls">
              <label className="journey-tracker__label">Catatan titik <span>(opsional)</span>
                <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Contoh: rest area atau pelabuhan" disabled={checkingIn || finishing} className="form-control" />
              </label>
              <button type="button" onClick={handleCheckIn} disabled={checkingIn || finishing} className="secondary-action">{checkingIn ? "Mengambil lokasi..." : checkpoints.length === 0 ? "Catat lokasi saat ini" : "Tambah titik perjalanan"}</button>
              <button type="button" onClick={handleFinish} disabled={checkingIn || finishing || checkpoints.length === 0} className="journey-tracker__finish">{finishing ? "Mengambil lokasi..." : "Tandai perjalanan selesai"}</button>
            </div>
          </>}

          {checkpoints.length > 0 && <div className="journey-tracker__timeline">
            <p>Riwayat perjalanan</p>
            <ol>{checkpoints.map((cp, index) => {
              const elapsedMs = new Date(cp.recorded_at).getTime() - new Date(checkpoints[0].recorded_at).getTime();
              return <li key={`${cp.recorded_at}-${index}`}><span>{index + 1}</span><div><strong>{cp.checkpoint_label || "Titik perjalanan"}</strong><small>{new Date(cp.recorded_at).toLocaleTimeString("id-ID")}{index > 0 && ` · +${formatDuration(elapsedMs)} sejak mulai`}</small></div></li>;
            })}</ol>
          </div>}

          {recap && <div className="journey-tracker__recap">
            <p>Rekap perjalanan</p><strong>{formatDuration(recap.totalMs)}</strong><span>{checkpoints.length} titik tercatat · selesai {new Date(recap.finishedAt).toLocaleTimeString("id-ID")}</span>
            <small>{reportingOutcome ? "Melaporkan hasil perjalanan..." : outcomeReported && reportedDelayHours !== null ? <>Keterlambatan tercatat: <b>{formatDuration(reportedDelayHours * 3_600_000)}</b> dibanding estimasi rute.</> : "Menyiapkan laporan hasil perjalanan."}</small>
          </div>}
        </div>
      )}
      {error && <p className="journey-tracker__error" role="alert">{error}</p>}
    </section>
  );
}
