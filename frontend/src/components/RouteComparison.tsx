import RiskBadge from "@/components/RiskBadge";
import type { RankingPreference, RouteCandidate } from "@/lib/types";

const MODE_LABELS: Record<string, string> = {
  darat: "Darat",
  laut: "Laut",
  kombinasi: "Kombinasi",
};

const ENVIRONMENT_LABELS: Record<RouteCandidate["environmental_data_quality"], string> = {
  forecast: "Prakiraan eksternal",
  partial: "Sebagian fallback",
  fallback: "Fallback netral",
  configured: "Default terkonfigurasi",
};

const CARGO_TEMPERATURE_LABELS: Record<RouteCandidate["cargo_temperature_data_quality"], string> = {
  assumed: "Suhu ideal diasumsikan",
  forecast: "Prakiraan eksternal",
  mixed: "Prakiraan + sintetis",
  synthetic: "Fallback sintetis",
  unavailable: "Tidak tersedia",
};

function minimumBy(routes: RouteCandidate[], value: (route: RouteCandidate) => number): RouteCandidate {
  return routes.reduce((best, route) => (value(route) < value(best) ? route : best));
}

function deltaLabel(value: number, unit: string, digits = 1): string {
  if (Math.abs(value) < 10 ** -digits) return "terbaik";
  return `+${value.toFixed(digits)} ${unit}`;
}

function decisionSummary(routes: RouteCandidate[], ranking: RankingPreference): string {
  const recommended = routes[0];
  const fastest = minimumBy(routes, (route) => route.estimated_duration_hours);
  const lowestScore = minimumBy(routes, (route) => route.risk_probability);

  if (ranking === "risiko") {
    if (recommended.route_id === fastest.route_id) {
      return "Rute rekomendasi juga merupakan kandidat tercepat pada hasil ini.";
    }
    const extraHours = recommended.estimated_duration_hours - fastest.estimated_duration_hours;
    const scoreDifference = (fastest.risk_probability - recommended.risk_probability) * 100;
    if (scoreDifference > 0) {
      return `Rute rekomendasi membutuhkan ${extraHours.toFixed(1)} jam lebih lama, dengan skor risiko model ${scoreDifference.toFixed(1)} poin lebih rendah daripada kandidat tercepat.`;
    }
    return `Rute rekomendasi membutuhkan ${extraHours.toFixed(1)} jam lebih lama karena kategori risiko dan aturan pemeringkatan backend, bukan karena durasi tercepat.`;
  }

  if (recommended.route_id === lowestScore.route_id) {
    return "Kandidat tercepat yang direkomendasikan juga memiliki skor risiko model terendah pada hasil ini.";
  }
  const savedHours = lowestScore.estimated_duration_hours - recommended.estimated_duration_hours;
  const extraScore = (recommended.risk_probability - lowestScore.risk_probability) * 100;
  return `Preferensi kecepatan menghemat ${Math.max(0, savedHours).toFixed(1)} jam, dengan skor risiko model ${Math.max(0, extraScore).toFixed(1)} poin lebih tinggi daripada kandidat berskor terendah.`;
}

export default function RouteComparison({
  routes,
  recommendedRouteId,
  rankingPreference,
  selectedRouteId,
  onSelectRoute,
}: {
  routes: RouteCandidate[];
  recommendedRouteId: string;
  rankingPreference: RankingPreference;
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
}) {
  if (routes.length < 2) return null;

  const fastest = minimumBy(routes, (route) => route.estimated_duration_hours);
  const shortest = minimumBy(routes, (route) => route.distance_km);
  const lowestScore = minimumBy(routes, (route) => route.risk_probability);

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            Perbandingan Rute
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-zinc-700 dark:text-zinc-300">
            {decisionSummary(routes, rankingPreference)}
          </p>
        </div>
        <span className="rounded-full bg-zinc-100 px-3 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          Dasar rekomendasi: {rankingPreference === "risiko" ? "risiko" : "kecepatan"}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-sm">
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 w-44 border-b border-zinc-200 bg-white p-3 text-xs font-medium uppercase tracking-wide text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
                Parameter
              </th>
              {routes.map((route) => (
                <th scope="col" key={route.route_id} className="border-b border-zinc-200 p-3 align-top dark:border-zinc-700">
                  <button
                    type="button"
                    aria-pressed={selectedRouteId === route.route_id}
                    onClick={() => onSelectRoute(route.route_id)}
                    className={`w-full rounded-md border p-3 text-left transition-colors ${
                      selectedRouteId === route.route_id
                        ? "border-sky-500 bg-sky-50 dark:border-sky-500 dark:bg-sky-950"
                        : "border-zinc-200 hover:border-sky-300 dark:border-zinc-700 dark:hover:border-sky-700"
                    }`}
                  >
                    <span className="block font-semibold text-zinc-900 dark:text-zinc-100">
                      {MODE_LABELS[route.transport_mode] ?? route.transport_mode}
                    </span>
                    <span className="mt-0.5 block text-xs font-normal text-zinc-500 dark:text-zinc-400">
                      {route.route_id}
                    </span>
                    <span className="mt-2 flex flex-wrap gap-1">
                      {route.route_id === recommendedRouteId && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                          Direkomendasikan
                        </span>
                      )}
                      {route.route_id === fastest.route_id && (
                        <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[11px] text-sky-800 dark:bg-sky-950 dark:text-sky-300">
                          Tercepat
                        </span>
                      )}
                      {route.route_id === lowestScore.route_id && (
                        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[11px] text-violet-800 dark:bg-violet-950 dark:text-violet-300">
                          Skor terendah
                        </span>
                      )}
                    </span>
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="text-zinc-700 dark:text-zinc-300">
            <tr>
              <th scope="row" className="sticky left-0 border-b border-zinc-100 bg-white p-3 font-medium dark:border-zinc-800 dark:bg-zinc-900">
                Risiko model
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="border-b border-zinc-100 p-3 dark:border-zinc-800">
                  <div className="flex items-center gap-2">
                    <RiskBadge level={route.risk_level} />
                    <span>{(route.risk_probability * 100).toFixed(1)}%</span>
                  </div>
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="sticky left-0 border-b border-zinc-100 bg-white p-3 font-medium dark:border-zinc-800 dark:bg-zinc-900">
                Durasi
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="border-b border-zinc-100 p-3 dark:border-zinc-800">
                  {route.estimated_duration_hours.toFixed(1)} jam{" "}
                  <span className="text-xs text-zinc-500">
                    ({deltaLabel(route.estimated_duration_hours - fastest.estimated_duration_hours, "jam")})
                  </span>
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="sticky left-0 border-b border-zinc-100 bg-white p-3 font-medium dark:border-zinc-800 dark:bg-zinc-900">
                Jarak
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="border-b border-zinc-100 p-3 dark:border-zinc-800">
                  {route.distance_km.toFixed(0)} km{" "}
                  <span className="text-xs text-zinc-500">
                    ({deltaLabel(route.distance_km - shortest.distance_km, "km", 0)})
                  </span>
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="sticky left-0 border-b border-zinc-100 bg-white p-3 font-medium dark:border-zinc-800 dark:bg-zinc-900">
                Routing
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="border-b border-zinc-100 p-3 dark:border-zinc-800">
                  {route.data_quality === "estimated" ? "Fallback estimasi" : "Tanpa fallback"}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="sticky left-0 border-b border-zinc-100 bg-white p-3 font-medium dark:border-zinc-800 dark:bg-zinc-900">
                Data lingkungan
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="border-b border-zinc-100 p-3 dark:border-zinc-800">
                  {ENVIRONMENT_LABELS[route.environmental_data_quality]}
                </td>
              ))}
            </tr>
            <tr>
              <th scope="row" className="sticky left-0 bg-white p-3 font-medium dark:bg-zinc-900">
                Suhu kargo
              </th>
              {routes.map((route) => (
                <td key={route.route_id} className="p-3">
                  {CARGO_TEMPERATURE_LABELS[route.cargo_temperature_data_quality]}
                  {route.max_cargo_temp_excess_c > 0 && (
                    <span className="block text-xs text-amber-700 dark:text-amber-400">
                      +{route.max_cargo_temp_excess_c.toFixed(1)}°C di atas ideal
                    </span>
                  )}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
        Skor berasal dari model yang dilatih dengan data sintetis dan belum merupakan probabilitas kerusakan yang tervalidasi.
        Klik judul kandidat untuk menyorot rute yang sama di peta dan kartu detail.
      </p>
    </section>
  );
}
