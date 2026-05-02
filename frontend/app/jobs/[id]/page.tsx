"use client";

import { use, useEffect, useState } from "react";

import { FitBadge } from "@/components/feed/FitBadge";
import { TrustBreakdown } from "@/components/feed/TrustBreakdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getJobDetail, type JobOut } from "@/lib/api";

export default function JobDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [job, setJob] = useState<JobOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const j = await getJobDetail(Number(id));
        if (!cancelled) setJob(j);
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-8">
        <p className="text-sm text-neutral-500">Loading…</p>
      </main>
    );
  }
  if (error || !job) {
    return (
      <main className="mx-auto max-w-6xl px-6 py-8">
        <p className="text-sm text-red-600">{error ?? "Job not found"}</p>
      </main>
    );
  }

  const fit = job.fit_assessment;
  const skills = fit?.skills_match_json;
  const knockouts = fit?.knockout_risks_json ?? [];

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-12 gap-6 px-6 py-8">
      {/* Left: summary */}
      <aside className="col-span-12 space-y-4 lg:col-span-4">
        <header>
          <h1 className="text-2xl font-semibold leading-tight">{job.title}</h1>
          <p className="mt-1 text-sm text-neutral-700">{job.company}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
            {job.location && <span>{job.location}</span>}
            {job.work_mode && <span>· {job.work_mode}</span>}
            {job.salary_text && <span>· {job.salary_text}</span>}
            {job.ats_family && <span>· {job.ats_family}</span>}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {job.sources.map((s, i) => (
              <Badge key={i} variant="secondary" className="text-[10px]">
                {s.source_provider}
              </Badge>
            ))}
          </div>
        </header>

        {fit && (
          <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-4">
            <h2 className="text-sm font-semibold">Fit assessment</h2>
            <FitBadge
              verdict={fit.verdict}
              detail={skills?.score_required ?? undefined}
            />
            {fit.summary_md && (
              <p className="text-sm text-neutral-700">{fit.summary_md}</p>
            )}

            {skills && (
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="font-medium text-emerald-700">Present</p>
                  <ul className="mt-1 space-y-0.5">
                    {skills.present.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="font-medium text-amber-800">Missing</p>
                  <ul className="mt-1 space-y-0.5">
                    {skills.missing.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {fit.experience_verdict && (
              <Dimension label="Experience" value={fit.experience_verdict} />
            )}
            {fit.domain_match && (
              <Dimension label="Domain" value={fit.domain_match} />
            )}
            {fit.evidence_strength && (
              <Dimension label="Evidence" value={fit.evidence_strength} />
            )}
          </section>
        )}

        {job.trust_assessment && (
          <TrustBreakdown trust={job.trust_assessment} />
        )}

        {knockouts.length > 0 && (
          <section className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-4">
            <h2 className="text-sm font-semibold text-amber-900">
              Knockout questions
            </h2>
            <ul className="space-y-2">
              {knockouts.map((k, i) => (
                <li key={i} className="text-xs text-amber-900">
                  <span className="font-medium">{k.question}</span>
                  <br />
                  <span className="text-amber-700">
                    Your status: {k.user_status} · {k.can_pass}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </aside>

      {/* Center: description */}
      <section className="col-span-12 space-y-3 lg:col-span-5">
        <h2 className="text-sm font-semibold text-neutral-700">Description</h2>
        <article className="prose prose-sm max-w-none whitespace-pre-wrap rounded-lg border border-neutral-200 bg-white p-5 text-sm leading-relaxed">
          {job.description_md ?? (
            <p className="text-neutral-400">No description available.</p>
          )}
        </article>
      </section>

      {/* Right: actions (placeholder until later phases land) */}
      <aside className="col-span-12 space-y-2 lg:col-span-3">
        <div className="space-y-2 rounded-lg border border-neutral-200 bg-white p-4">
          <h2 className="text-sm font-semibold">Actions</h2>
          {job.apply_url && (
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer">
              <Button className="w-full" variant="default">
                Open ATS
              </Button>
            </a>
          )}
          <Button className="w-full" variant="outline" disabled>
            Tailor resume (Phase 4)
          </Button>
          <Button className="w-full" variant="outline" disabled>
            Find contacts (Phase 6)
          </Button>
          <Button className="w-full" variant="outline" disabled>
            Draft outreach (Phase 7)
          </Button>
        </div>
      </aside>
    </main>
  );
}

function Dimension({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-xs">
      <p className="font-medium text-neutral-700">{label}</p>
      <p className="mt-0.5 text-neutral-600">{value}</p>
    </div>
  );
}
