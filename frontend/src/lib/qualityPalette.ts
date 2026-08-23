// Fixed status palette for quality_status (Baik/Menurun/Kritis), same hex in
// light/dark -- mirrors riskPalette.ts's convention for risk_level.
export const QUALITY_COLORS: Record<string, string> = {
  Baik: "#0ca30c",
  Menurun: "#fab219",
  Kritis: "#d03b3b",
};

export function qualityColor(status: string): string {
  return QUALITY_COLORS[status] ?? "#898781";
}
