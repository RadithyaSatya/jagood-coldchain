import { WAVE_SCALE, waveColor } from "@/lib/wavePalette";
import type { RouteCandidate } from "@/lib/types";

export default function ParameterLegend({ route }: { route?: RouteCandidate }) {
  return (
    <aside className="map-forecast-panel" aria-label="Keterangan prakiraan gelombang">
      <div className="map-forecast-panel__summary">
        <span className="map-forecast-panel__eyebrow">Prakiraan gelombang</span>
        {route ? (
          <span className="wave-reading">
            <i aria-hidden style={{ backgroundColor: waveColor(route.wave_height_m) }} />
            {route.wave_height_m.toFixed(1)} m · {route.wave_category}
          </span>
        ) : (
          <span className="wave-reading">Pilih rute untuk melihat kondisi</span>
        )}
      </div>
      <details className="map-forecast-panel__details">
        <summary>Lihat skala tinggi gelombang</summary>
        <ul className="wave-scale">
          {WAVE_SCALE.map((band) => (
            <li key={band.label}>
              <i aria-hidden style={{ backgroundColor: band.color }} />
              <span>{band.label}</span>
              <small>{band.range}</small>
            </li>
          ))}
        </ul>
        <p>Warna lapisan luar rute laut menunjukkan tinggi gelombang. Garis tengah tetap menunjukkan risiko rute.</p>
      </details>
    </aside>
  );
}
