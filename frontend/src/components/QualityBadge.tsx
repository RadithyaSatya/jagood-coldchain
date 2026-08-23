import { qualityColor } from "@/lib/qualityPalette";

export default function QualityBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-semibold text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
      <span
        aria-hidden
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: qualityColor(status) }}
      />
      {status}
    </span>
  );
}
