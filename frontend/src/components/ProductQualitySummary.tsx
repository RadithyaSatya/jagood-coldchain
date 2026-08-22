import type { RouteCandidate } from "@/lib/types";

export default function ProductQualitySummary({ route }: { route: RouteCandidate }) {
  const remainingHours = route.estimated_remaining_shelf_life_hours;
  const remainingPercent = route.estimated_remaining_shelf_life_percent;
  const retention = route.quality_retention_proxy;

  if (remainingHours === undefined && remainingPercent === undefined && retention === undefined) return null;

  return (
    <div className="mt-3 rounded border border-teal-200 bg-teal-50 px-3 py-2 dark:border-teal-900 dark:bg-teal-950/30">
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-800 dark:text-teal-300">
        Estimasi kualitas produk
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-2 text-sm text-zinc-700 dark:text-zinc-300 sm:grid-cols-3">
        {remainingHours !== undefined && (
          <div>
            <dt className="text-xs text-zinc-500">Sisa umur simpan</dt>
            <dd className="font-medium">{remainingHours.toFixed(1)} jam</dd>
          </div>
        )}
        {remainingPercent !== undefined && (
          <div>
            <dt className="text-xs text-zinc-500">Sisa relatif</dt>
            <dd className="font-medium">{remainingPercent.toFixed(1)}%</dd>
          </div>
        )}
        {retention !== undefined && (
          <div>
            <dt className="text-xs text-zinc-500">Quality-retention proxy</dt>
            <dd className="font-medium">{retention.toFixed(1)}%</dd>
          </div>
        )}
      </dl>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
        Proxy berbasis suhu dan durasi untuk perbandingan skenario, bukan pengukuran mutu atau jaminan keamanan pangan.
        {route.quality_estimation_data_quality && ` Kualitas data: ${route.quality_estimation_data_quality}.`}
      </p>
    </div>
  );
}
