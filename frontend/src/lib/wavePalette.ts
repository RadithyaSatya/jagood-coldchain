export const WAVE_SCALE = [
  { label: "Tenang", range: "0–0.5 m", color: "#2563eb", max: 0.5 },
  { label: "Rendah", range: "0.5–1.25 m", color: "#22c55e", max: 1.25 },
  { label: "Sedang", range: "1.25–2.5 m", color: "#eab308", max: 2.5 },
  { label: "Tinggi", range: "2.5–4 m", color: "#f97316", max: 4 },
  { label: "Sangat tinggi", range: "4–6 m", color: "#ef4444", max: 6 },
  { label: "Ekstrem", range: "> 6 m", color: "#7f1d1d", max: Infinity },
] as const;

export function waveColor(waveHeightM: number): string {
  return WAVE_SCALE.find((band) => waveHeightM <= band.max)?.color ?? WAVE_SCALE[WAVE_SCALE.length - 1].color;
}
