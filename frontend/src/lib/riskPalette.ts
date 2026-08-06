// Fixed status palette (validated colorblind-safe, same hex in light/dark --
// status colors are never themed). Shared by RiskBadge and the map so a risk
// level always means the same color everywhere in the UI.
export const RISK_COLORS: Record<string, string> = {
  Low: "#0ca30c",
  Medium: "#fab219",
  High: "#d03b3b",
};

export const RISK_LABELS: Record<string, string> = {
  Low: "Rendah",
  Medium: "Sedang",
  High: "Tinggi",
};

export function riskColor(level: string): string {
  return RISK_COLORS[level] ?? "#898781";
}
