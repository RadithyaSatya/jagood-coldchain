import type { RouteCandidate } from "@/lib/types";

const WIDTH = 320;
const HEIGHT = 104;
const PAD_LEFT = 34;
const PAD_RIGHT = 12;
const PAD_TOP = 14;
const PAD_BOTTOM = 22;

export default function CargoTempChart({ route }: { route: RouteCandidate }) {
  const profile = route.cargo_temp_profile;
  if (route.cold_chain_equipment !== "pasif" || profile.length === 0) return null;

  const ideal = route.commodity_temp_ideal_c ?? profile[0].temp_c;
  const hours = profile.map((p) => p.hour);
  const temps = profile.map((p) => p.temp_c);
  const maxHour = Math.max(...hours, 1);
  const minTemp = Math.min(...temps, ideal);
  const maxTemp = Math.max(...temps, ideal);
  const tempPad = Math.max(1, (maxTemp - minTemp) * 0.15);
  const yMin = minTemp - tempPad;
  const yMax = maxTemp + tempPad;

  const x = (h: number) => PAD_LEFT + (h / maxHour) * (WIDTH - PAD_LEFT - PAD_RIGHT);
  const y = (t: number) => PAD_TOP + (1 - (t - yMin) / (yMax - yMin)) * (HEIGHT - PAD_TOP - PAD_BOTTOM);

  const linePath = profile.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.hour)} ${y(p.temp_c)}`).join(" ");
  const idealY = y(ideal);

  const areaAboveIdeal = `M ${x(profile[0].hour)} ${idealY} ` +
    profile.map((p) => `L ${x(p.hour)} ${Math.min(y(p.temp_c), idealY)}`).join(" ") +
    ` L ${x(profile[profile.length - 1].hour)} ${idealY} Z`;

  const last = profile[profile.length - 1];

  return (
    <div className="mt-3 border-t border-slate-200 pt-3">
      <p className="mb-1 text-xs font-medium text-slate-500">
        Simulasi suhu kargo sepanjang perjalanan (tanpa reefer)
      </p>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="cargo-temp-chart" role="img" aria-label="Grafik suhu kargo terhadap waktu">
        <line
          x1={PAD_LEFT} y1={idealY} x2={WIDTH - PAD_RIGHT} y2={idealY}
          stroke="#898781" strokeWidth={1} strokeDasharray="3 3"
        />
        <text x={PAD_LEFT} y={idealY - 4} fontSize={9} fill="#898781">
          ideal {ideal.toFixed(1)}°C
        </text>

        <path d={areaAboveIdeal} fill="#d03b3b" opacity={0.1} />

        <path d={linePath} fill="none" stroke="#2a78d6" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {profile.map((p, i) => (
          <circle key={i} cx={x(p.hour)} cy={y(p.temp_c)} r={4} fill="#2a78d6" stroke="white" strokeWidth={2} />
        ))}
        <text x={x(last.hour) - 4} y={y(last.temp_c) - 8} fontSize={10} fontWeight={600} fill="#2a78d6" textAnchor="end">
          {last.temp_c.toFixed(1)}°C
        </text>

        <text x={PAD_LEFT} y={HEIGHT - 4} fontSize={9} fill="#898781">0 jam</text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 4} fontSize={9} fill="#898781" textAnchor="end">
          {maxHour.toFixed(0)} jam
        </text>
      </svg>
      {route.max_cargo_temp_excess_c > 0 && (
        <p className="text-xs text-red-700">
          Suhu kargo diperkirakan melebihi suhu ideal hingga {route.max_cargo_temp_excess_c.toFixed(1)}°C selama perjalanan.
        </p>
      )}
      <p
        className={`text-xs ${
          route.quality_status === "Baik"
            ? "text-zinc-500 dark:text-zinc-400"
            : "text-red-700 dark:text-red-400"
        }`}
      >
        Sisa umur simpan diperkirakan {route.remaining_shelf_life_hours.toFixed(1)} jam (
        {route.remaining_shelf_life_pct.toFixed(0)}%, {route.quality_status}) -- proxy MVP, bukan jaminan keamanan pangan.
      </p>
    </div>
  );
}
