import type { TrustAssessmentOut } from "@/lib/api";

export function TrustBreakdown({ trust }: { trust: TrustAssessmentOut }) {
  // Only render the full breakdown for concerning verdicts.
  if (trust.verdict !== "suspicious" && trust.verdict !== "likely_scam") {
    return null;
  }

  const tone =
    trust.verdict === "likely_scam"
      ? "border-red-300 bg-red-50"
      : "border-amber-300 bg-amber-50";

  return (
    <section
      className={`space-y-3 rounded-lg border ${tone} p-4 text-xs`}
      aria-label="Trust breakdown"
    >
      <h2 className="text-sm font-semibold">
        Trust check · {trust.verdict.replace("_", " ")}
      </h2>

      {trust.rationale_md && (
        <p className="whitespace-pre-wrap text-neutral-700">
          {trust.rationale_md}
        </p>
      )}

      {(trust.scam_signals_json?.length ?? 0) > 0 && (
        <SignalGroup
          title="Scam signals"
          signals={trust.scam_signals_json ?? []}
        />
      )}

      {(trust.ghost_job_signals_json?.length ?? 0) > 0 && (
        <SignalGroup
          title="Ghost-job signals"
          signals={trust.ghost_job_signals_json ?? []}
        />
      )}

      {(trust.positive_signals_json?.length ?? 0) > 0 && (
        <SignalGroup
          title="Positive signals"
          signals={trust.positive_signals_json ?? []}
        />
      )}
    </section>
  );
}

function SignalGroup({
  title,
  signals,
}: {
  title: string;
  signals: { description: string; severity: string; source?: string }[];
}) {
  return (
    <div>
      <p className="font-medium">{title}</p>
      <ul className="mt-1 space-y-1">
        {signals.map((s, i) => (
          <li key={i} className="text-neutral-700">
            <span className="opacity-60">[{s.severity}]</span> {s.description}
            {s.source && (
              <span className="ml-1.5 text-[10px] text-neutral-400">
                ({s.source})
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
