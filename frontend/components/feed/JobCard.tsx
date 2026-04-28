import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { FitBadge } from "@/components/feed/FitBadge";
import type { JobOut } from "@/lib/api";

export function JobCard({ job }: { job: JobOut }) {
  const fit = job.fit_assessment;
  const skillsScore = fit?.skills_match_json?.score_required;
  const knockouts = (fit?.knockout_risks_json ?? []).filter(
    (k) => k.can_pass === "no" || k.can_pass === "maybe",
  );

  return (
    <li className="rounded-lg border border-neutral-200 bg-white p-4 transition-colors hover:border-neutral-300">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-1">
          <h3 className="text-base font-medium leading-tight">
            <Link href={`/jobs/${job.id}`} className="hover:underline">
              {job.title}
            </Link>
          </h3>
          <p className="text-sm text-neutral-700">{job.company}</p>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
            {job.location && <span>{job.location}</span>}
            {job.work_mode && <span>· {job.work_mode}</span>}
            {job.salary_text && <span>· {job.salary_text}</span>}
            {job.ats_family && <span>· {job.ats_family}</span>}
          </div>

          {fit && (
            <div className="pt-2">
              <FitBadge verdict={fit.verdict} detail={skillsScore ?? undefined} />
              {fit.summary_md && (
                <p className="mt-1.5 text-xs text-neutral-600">
                  {fit.summary_md}
                </p>
              )}
            </div>
          )}

          {knockouts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1.5">
              {knockouts.map((k, i) => (
                <span
                  key={i}
                  className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[11px] text-amber-800"
                  title={k.question}
                >
                  ⚠ {k.criterion} · {k.can_pass}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-shrink-0 flex-col items-end gap-1">
          {job.sources.map((s, i) => (
            <Badge key={i} variant="secondary" className="text-[10px]">
              {s.source_provider}
            </Badge>
          ))}
        </div>
      </div>
    </li>
  );
}
