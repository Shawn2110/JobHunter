import type { TrustVerdict } from "@/lib/api";

const STYLES: Record<
  TrustVerdict,
  { bg: string; text: string; label: string } | null
> = {
  // Per Design.md § 4.3 — only suspicious/likely_scam show a badge.
  // Verified, likely_real, unknown render NO badge — the absence is the signal.
  verified: null,
  likely_real: null,
  unknown: null,
  suspicious: {
    bg: "bg-amber-100",
    text: "text-amber-800",
    label: "⚠ Suspicious",
  },
  likely_scam: {
    bg: "bg-red-100",
    text: "text-red-800",
    label: "⚠ Likely scam",
  },
};

export function TrustBadge({
  verdict,
  reason,
}: {
  verdict: TrustVerdict;
  reason?: string | null;
}) {
  const style = STYLES[verdict];
  if (!style) return null;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
      {reason && <span className="ml-1.5 font-normal opacity-80">· {reason}</span>}
    </span>
  );
}
