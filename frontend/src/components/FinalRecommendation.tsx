import RiskBadge from "@/components/RiskBadge";
import { environmentalDataLabel } from "@/lib/dataProvenance";
import type { RankingPreference, RouteCandidate, ScenarioResponse } from "@/lib/types";

const MODE_LABELS: Record<string, string> = {
  darat: "darat",
  laut: "laut",
  kombinasi: "kombinasi darat dan laut",
};

function formatArrival(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleString("id-ID", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function routeDecision(route: RouteCandidate, ranking: RankingPreference): string {
  const basis = ranking === "risiko" ? "skor risiko model terendah" : "waktu tempuh tercepat";
  return `Gunakan kandidat ${MODE_LABELS[route.transport_mode] ?? route.transport_mode} sebagai rute utama berdasarkan ${basis}.`;
}

export default function FinalRecommendation({
  route,
  rankingPreference,
  scenario,
}: {
  route: RouteCandidate;
  rankingPreference: RankingPreference;
  scenario: ScenarioResponse | null;
}) {
  const scenarioDelta = scenario ? scenario.risk_delta * 100 : null;

  return (
    <section className="rounded-lg border-2 border-emerald-300 bg-emerald-50 p-5 dark:border-emerald-800 dark:bg-emerald-950/30">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-400">
            Final Recommendation
          </p>
          <h2 className="mt-1 text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {routeDecision(route, rankingPreference)}
          </h2>
        </div>
        <RiskBadge level={route.risk_level} />
      </div>

      <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">{route.risk_explanation_summary}</p>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Moda</dt>
          <dd className="font-medium text-zinc-900 dark:text-zinc-100">
            {MODE_LABELS[route.transport_mode] ?? route.transport_mode}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Skor risiko</dt>
          <dd className="font-medium text-zinc-900 dark:text-zinc-100">
            {(route.risk_probability * 100).toFixed(1)}%
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Estimasi tiba</dt>
          <dd className="font-medium text-zinc-900 dark:text-zinc-100">{formatArrival(route.estimated_arrival)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Sumber lingkungan</dt>
          <dd className="font-medium text-zinc-900 dark:text-zinc-100">{environmentalDataLabel(route)}</dd>
        </div>
      </dl>

      {route.estimated_remaining_shelf_life_hours !== undefined && (
        <p className="mt-3 text-sm text-zinc-700 dark:text-zinc-300">
          Estimasi sisa umur simpan: <strong>{route.estimated_remaining_shelf_life_hours.toFixed(1)} jam</strong>
          {route.estimated_remaining_shelf_life_percent !== undefined
            ? ` (${route.estimated_remaining_shelf_life_percent.toFixed(1)}%)`
            : ""}
          . Nilai ini merupakan proxy, bukan jaminan mutu.
        </p>
      )}

      {scenario && scenarioDelta !== null ? (
        <div className="mt-4 rounded border border-violet-200 bg-white px-4 py-3 text-sm dark:border-violet-900 dark:bg-zinc-950">
          <p className="font-medium text-zinc-900 dark:text-zinc-100">Evaluasi skenario terbaru</p>
          <p className="mt-1 text-zinc-700 dark:text-zinc-300">
            Perubahan skor risiko: {scenarioDelta > 0 ? "+" : ""}{scenarioDelta.toFixed(2)} poin persentase. {scenario.recommendation}
          </p>
        </div>
      ) : (
        <p className="mt-4 text-xs text-zinc-600 dark:text-zinc-400">
          Jalankan Scenario Simulator untuk melengkapi rekomendasi ini dengan dampak gangguan operasional.
        </p>
      )}

      <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
        Ringkasan ini menyatukan hasil terstruktur route planner dan scenario simulator; tidak melakukan perhitungan baru.
      </p>
    </section>
  );
}
