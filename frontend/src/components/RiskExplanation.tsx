import type { RiskFactor } from "@/lib/types";

export default function RiskExplanation({ summary, factors }: { summary: string; factors: RiskFactor[] }) {
  return (
    <div className="mt-3 border-t border-zinc-100 pt-3 dark:border-zinc-800">
      <p className="text-sm text-zinc-700 dark:text-zinc-300">{summary}</p>
      {factors.length > 0 && (
        <ul className="mt-2 space-y-1">
          {factors.map((f, i) => (
            <li key={i} className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">
              <span
                aria-hidden
                className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  f.effect === "menaikkan"
                    ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
                    : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                }`}
              >
                {f.effect === "menaikkan" ? "+" : "-"}
              </span>
              {f.factor}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
