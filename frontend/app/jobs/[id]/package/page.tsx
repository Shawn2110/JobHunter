"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, use, useCallback, useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  createCoverLetter,
  createCustomAnswers,
  createTailoringBrief,
  executeTailoring,
  getJobDetail,
  listJobArtifacts,
  type ArtifactOut,
  type BriefOut,
  type CustomAnswerOut,
  type JobOut,
} from "@/lib/api";

type AsyncState =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "ok" }
  | { kind: "error"; message: string };

export default function PackagePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <Suspense
      fallback={
        <main className="mx-auto max-w-4xl px-6 py-8">
          <p className="text-sm text-neutral-500">Loading…</p>
        </main>
      }
    >
      <PackagePageInner params={params} />
    </Suspense>
  );
}

function PackagePageInner({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const jobId = Number(id);
  const searchParams = useSearchParams();
  const isGenerating = searchParams.get("gen") === "1";

  const [job, setJob] = useState<JobOut | null>(null);
  const [, setArtifacts] = useState<ArtifactOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [resumeBrief, setResumeBrief] = useState<BriefOut | null>(null);
  const [resumeArtifact, setResumeArtifact] = useState<ArtifactOut | null>(null);
  const [resumeState, setResumeState] = useState<AsyncState>({ kind: "idle" });

  const [coverArtifact, setCoverArtifact] = useState<ArtifactOut | null>(null);
  const [coverBrief, setCoverBrief] = useState<BriefOut | null>(null);
  const [coverState, setCoverState] = useState<AsyncState>({ kind: "idle" });

  const [customAnswers, setCustomAnswers] = useState<CustomAnswerOut[]>([]);
  const [customState, setCustomState] = useState<AsyncState>({ kind: "idle" });

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollDeadlineRef = useRef<number | null>(null);

  const refresh = useCallback(async (): Promise<Set<string>> => {
    const kinds = new Set<string>();
    try {
      const [j, arts] = await Promise.all([
        getJobDetail(jobId),
        listJobArtifacts(jobId),
      ]);
      setJob(j);
      setArtifacts(arts);
      const resume = arts.find((a) => a.kind === "resume");
      if (resume) {
        setResumeArtifact(resume);
        setResumeState({ kind: "ok" });
        kinds.add("resume");
      }
      const cover = arts.find((a) => a.kind === "cover_letter");
      if (cover) {
        setCoverArtifact(cover);
        setCoverState({ kind: "ok" });
        kinds.add("cover_letter");
      }
      const ca = arts.find((a) => a.kind === "custom_answers");
      if (ca && ca.content_json && Array.isArray(ca.content_json["answers"])) {
        setCustomAnswers(ca.content_json["answers"] as CustomAnswerOut[]);
        setCustomState({ kind: "ok" });
        kinds.add("custom_answers");
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
    return kinds;
  }, [jobId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // When ?gen=1 is set, the extension just kicked off background tailoring.
  // Mark each empty section as "running" up-front and poll until all three
  // artifact kinds arrive (or we hit the 120s deadline).
  useEffect(() => {
    if (!isGenerating) return;
    pollDeadlineRef.current = Date.now() + 120_000;

    setResumeState((s) => (s.kind === "idle" ? { kind: "running" } : s));
    setCoverState((s) => (s.kind === "idle" ? { kind: "running" } : s));
    setCustomState((s) => (s.kind === "idle" ? { kind: "running" } : s));

    const tick = async () => {
      const kinds = await refresh();
      const allDone =
        kinds.has("resume") &&
        kinds.has("cover_letter") &&
        kinds.has("custom_answers");
      const timedOut =
        pollDeadlineRef.current !== null &&
        Date.now() >= pollDeadlineRef.current;
      if (allDone || timedOut) {
        if (pollTimerRef.current) {
          clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
        if (timedOut && !allDone) {
          setResumeState((s) =>
            s.kind === "running"
              ? { kind: "error", message: "Background tailoring timed out — try Regenerate." }
              : s,
          );
          setCoverState((s) =>
            s.kind === "running"
              ? { kind: "error", message: "Background tailoring timed out — try Regenerate." }
              : s,
          );
          setCustomState((s) =>
            s.kind === "running"
              ? { kind: "error", message: "Background tailoring timed out — try Regenerate." }
              : s,
          );
        }
      }
    };

    pollTimerRef.current = setInterval(() => void tick(), 5_000);
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isGenerating, refresh]);

  // ── Resume tailoring (two-step: brief → execute) ──────────────────────

  async function handleGenerateResume() {
    setResumeState({ kind: "running" });
    try {
      const brief = await createTailoringBrief(jobId);
      setResumeBrief(brief);
      const artifact = await executeTailoring(brief.id);
      setResumeArtifact(artifact);
      setResumeState({ kind: "ok" });
    } catch (err) {
      setResumeState({ kind: "error", message: (err as Error).message });
    }
  }

  // ── Cover letter (one-shot) ────────────────────────────────────────────

  async function handleGenerateCover() {
    setCoverState({ kind: "running" });
    try {
      const out = await createCoverLetter(jobId);
      setCoverBrief(out.brief);
      setCoverArtifact(out.artifact);
      setCoverState({ kind: "ok" });
    } catch (err) {
      setCoverState({ kind: "error", message: (err as Error).message });
    }
  }

  // ── Custom answers (5 in parallel) ─────────────────────────────────────

  async function handleGenerateCustom() {
    setCustomState({ kind: "running" });
    try {
      const out = await createCustomAnswers(jobId);
      setCustomAnswers(out.answers);
      setCustomState({ kind: "ok" });
    } catch (err) {
      setCustomState({ kind: "error", message: (err as Error).message });
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-8">
        <p className="text-sm text-neutral-500">Loading…</p>
      </main>
    );
  }
  if (error || !job) {
    return (
      <main className="mx-auto max-w-4xl px-6 py-8">
        <p className="text-sm text-red-600">{error ?? "Job not found"}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold leading-tight">
          Application package
        </h1>
        <p className="text-sm text-neutral-700">
          {job.title} · {job.company}
        </p>
        <div className="flex items-center gap-2 pt-2">
          {job.apply_url && (
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer">
              <Button>Open ATS application ↗</Button>
            </a>
          )}
          <a href={`/jobs/${job.id}`} className="text-xs text-neutral-500 hover:underline">
            ← Back to job detail
          </a>
        </div>
      </header>

      {/* ── Resume section ──────────────────────────────────────────── */}
      <Section
        title="Tailored resume"
        artifact={resumeArtifact}
        state={resumeState}
        onGenerate={handleGenerateResume}
        actionLabel="Generate tailored resume"
      >
        {resumeArtifact && (
          <ResumePane artifact={resumeArtifact} brief={resumeBrief} />
        )}
      </Section>

      {/* ── Cover letter section ────────────────────────────────────── */}
      <Section
        title="Cover letter"
        artifact={coverArtifact}
        state={coverState}
        onGenerate={handleGenerateCover}
        actionLabel="Generate cover letter"
      >
        {coverArtifact && (
          <CoverLetterPane artifact={coverArtifact} brief={coverBrief} />
        )}
      </Section>

      {/* ── Custom questions section ────────────────────────────────── */}
      <Section
        title="Custom-question answers"
        artifact={customAnswers.length > 0 ? ({ id: -1 } as ArtifactOut) : null}
        state={customState}
        onGenerate={handleGenerateCustom}
        actionLabel="Generate 5 standard answers"
      >
        {customAnswers.length > 0 && <CustomAnswersPane answers={customAnswers} />}
      </Section>
    </main>
  );
}

// ─── Section shell (header + generate-or-loading-or-content) ────────────

function Section({
  title,
  artifact,
  state,
  onGenerate,
  actionLabel,
  children,
}: {
  title: string;
  artifact: ArtifactOut | null;
  state: AsyncState;
  onGenerate: () => void;
  actionLabel: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-medium">{title}</h2>
        {artifact ? (
          <Badge variant="secondary">Generated</Badge>
        ) : state.kind === "running" ? (
          <Badge variant="secondary">Working…</Badge>
        ) : (
          <Badge variant="outline">Not generated</Badge>
        )}
      </div>

      {!artifact && state.kind === "idle" && (
        <Button onClick={onGenerate}>{actionLabel}</Button>
      )}

      {state.kind === "running" && (
        <p className="text-sm text-neutral-500">
          Generating… this takes 15-60 seconds.
        </p>
      )}

      {state.kind === "error" && (
        <div className="space-y-2">
          <p className="text-sm text-red-600">{state.message}</p>
          <Button variant="outline" size="sm" onClick={onGenerate}>
            Retry
          </Button>
        </div>
      )}

      {children}

      {artifact && (
        <div className="flex gap-2 pt-2">
          <Button size="sm" variant="outline" onClick={onGenerate}>
            Regenerate
          </Button>
        </div>
      )}
    </section>
  );
}

// ─── Resume pane ───────────────────────────────────────────────────────

function ResumePane({
  artifact,
  brief,
}: {
  artifact: ArtifactOut;
  brief: BriefOut | null;
}) {
  const truthOk = artifact.truthfulness_passed !== false;
  return (
    <div className="space-y-3">
      {!truthOk && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          <p className="font-medium">⚠ Truthfulness check did NOT pass</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {(artifact.truthfulness_violations_json ?? []).map((v, i) => (
              <li key={i}>{v}</li>
            ))}
          </ul>
          <p className="mt-2 text-amber-800">
            Review the rewritten resume carefully — the AI may have invented
            details. Regenerate or fall back to your master resume.
          </p>
        </div>
      )}
      {brief && (
        <details className="text-xs text-neutral-600">
          <summary className="cursor-pointer hover:text-neutral-900">
            View tailoring brief (strategy)
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded bg-neutral-50 p-3 font-mono">
            {JSON.stringify(brief.brief_json, null, 2)}
          </pre>
        </details>
      )}
      <ContentDisplay content={artifact.content_md ?? ""} />
    </div>
  );
}

// ─── Cover letter pane ────────────────────────────────────────────────

function CoverLetterPane({
  artifact,
  brief,
}: {
  artifact: ArtifactOut;
  brief: BriefOut | null;
}) {
  const wordCount =
    (artifact.content_json?.["word_count"] as number | undefined) ?? null;
  const reasoning =
    (artifact.content_json?.["reasoning_md"] as string | undefined) ?? null;
  return (
    <div className="space-y-3">
      {wordCount !== null && (
        <p className="text-xs text-neutral-500">{wordCount} words</p>
      )}
      <ContentDisplay content={artifact.content_md ?? ""} />
      {reasoning && (
        <details className="text-xs text-neutral-600">
          <summary className="cursor-pointer hover:text-neutral-900">
            Why these choices
          </summary>
          <p className="mt-2 whitespace-pre-wrap rounded bg-neutral-50 p-3">
            {reasoning}
          </p>
        </details>
      )}
      {brief && (
        <details className="text-xs text-neutral-600">
          <summary className="cursor-pointer hover:text-neutral-900">
            View brief
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto rounded bg-neutral-50 p-3 font-mono">
            {JSON.stringify(brief.brief_json, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

// ─── Custom answers pane ──────────────────────────────────────────────

function CustomAnswersPane({ answers }: { answers: CustomAnswerOut[] }) {
  return (
    <div className="space-y-3">
      {answers.map((a) => (
        <div key={a.key} className="space-y-1.5 rounded border border-neutral-200 p-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">{a.question}</p>
            <span className="text-xs text-neutral-400">{a.word_count}w</span>
          </div>
          <ContentDisplay content={a.answer_md} small />
        </div>
      ))}
    </div>
  );
}

// ─── Content display + copy button ─────────────────────────────────────

function ContentDisplay({
  content,
  small = false,
}: {
  content: string;
  small?: boolean;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API failures (e.g., insecure contexts) are silent;
      // user can select-and-copy manually.
    }
  }

  return (
    <div className="space-y-2">
      <pre
        className={`overflow-x-auto whitespace-pre-wrap rounded bg-neutral-50 p-4 font-sans leading-relaxed ${
          small ? "text-xs" : "text-sm"
        }`}
      >
        {content}
      </pre>
      <Button size="sm" variant="outline" onClick={() => void copy()}>
        {copied ? "✓ Copied" : "Copy to clipboard"}
      </Button>
    </div>
  );
}
