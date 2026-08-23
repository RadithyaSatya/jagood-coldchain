import { RISK_LABELS, riskColor } from "@/lib/riskPalette";

export default function RiskBadge({ level }: { level: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-800">
      <span
        aria-hidden
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: riskColor(level) }}
      />
      {RISK_LABELS[level] ?? level}
    </span>
  );
}
