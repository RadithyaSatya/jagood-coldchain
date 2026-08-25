import type { RiskFactor } from "@/lib/types";

export default function RiskExplanation({ summary, factors }: { summary: string; factors: RiskFactor[] }) {
  return (
    <div className="mt-3 border-t border-slate-200 pt-3">
      <p className="text-sm text-slate-700">{summary}</p>
      {factors.length > 0 && (
        <ul className="mt-2 space-y-1">
          {factors.map((f, i) => (
            <li key={i} className="flex items-center gap-2 text-xs text-slate-500">
              <span
                aria-hidden
                className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold ${
                  f.effect === "menaikkan"
                    ? "bg-red-100 text-red-700"
                    : "bg-emerald-100 text-emerald-700"
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
