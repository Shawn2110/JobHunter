import type { FitVerdict } from "@/lib/api";

const STYLES: Record<FitVerdict, { bg: string; text: string; label: string }> = {
  // Per Design.md § 5.2 — colors are paired with text labels, never used alone.
  strong: { bg: "bg-emerald-100", text: "text-emerald-800", label: "Strong fit" },
  good: { bg: "bg-blue-100", text: "text-blue-800", label: "Good fit" },
  stretch: { bg: "bg-amber-100", text: "text-amber-800", label: "Stretch" },
  below: { bg: "bg-neutral-100", text: "text-neutral-700", label: "Below your level" },
  mismatch: { bg: "bg-red-100", text: "text-red-800", label: "Mismatch" },
};

export function FitBadge({
  verdict,
  detail,
}: {
  verdict: FitVerdict;
  detail?: string | null;
}) {
  const style = STYLES[verdict];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
      {detail && <span className="ml-1.5 font-normal opacity-75">· {detail}</span>}
    </span>
  );
}
