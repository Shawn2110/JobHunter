"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchHealth,
  fetchProviders,
  type ProvidersResponse,
} from "@/lib/api";

type HealthStatus =
  | { kind: "loading" }
  | { kind: "ok"; providers: ProvidersResponse }
  | { kind: "error"; message: string };

export default function HomePage() {
  const [status, setStatus] = useState<HealthStatus>({ kind: "loading" });

  const probe = useCallback(async () => {
    setStatus({ kind: "loading" });
    try {
      await fetchHealth();
      const providers = await fetchProviders();
      setStatus({ kind: "ok", providers });
    } catch (err) {
      setStatus({ kind: "error", message: (err as Error).message });
    }
  }, []);

  useEffect(() => {
    void probe();
  }, [probe]);

  return (
    <main className="mx-auto max-w-2xl space-y-6 px-6 py-16">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">JobHunt</h1>
        <p className="text-sm text-neutral-500">
          Single-user, self-hosted, AI-augmented job hunt.
        </p>
      </div>

      <section className="space-y-3 rounded-lg border border-neutral-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Backend</span>
          <BackendStatusBadge status={status} />
        </div>

        {status.kind === "ok" && <ProvidersList providers={status.providers} />}

        {status.kind === "error" && (
          <div className="space-y-3">
            <p className="text-sm text-red-600">
              Backend unreachable: {status.message}. Is the FastAPI server
              running on{" "}
              <code className="rounded bg-neutral-100 px-1">
                {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}
              </code>
              ?
            </p>
            <Button size="sm" variant="outline" onClick={() => void probe()}>
              Retry
            </Button>
          </div>
        )}
      </section>

      <section className="space-y-3 rounded-lg border border-teal-200 bg-teal-50 p-5">
        <h2 className="text-sm font-semibold text-teal-900">
          Use the extension
        </h2>
        <p className="text-xs text-teal-900">
          The extension is the main JobHunt surface. Browse jobs on
          LinkedIn / Naukri / Indeed / Greenhouse / Lever / Ashby normally;
          the JobHunt overlay scores fit + flags scams + offers Save &amp;
          tailor on every job page you open.
        </p>
        <ol className="ml-4 list-decimal space-y-1 text-xs text-teal-900">
          <li>
            Visit <code className="rounded bg-white px-1">chrome://extensions</code>
          </li>
          <li>Enable Developer Mode (top-right toggle)</li>
          <li>
            Click <strong>Load unpacked</strong> and select the{" "}
            <code className="rounded bg-white px-1">extension/</code> folder
            in your JobHunt repo
          </li>
          <li>Open any job posting — the overlay appears top-right</li>
        </ol>
      </section>

      <section className="space-y-2 rounded-lg border border-neutral-200 bg-white p-5">
        <h2 className="text-sm font-semibold">This web app is for</h2>
        <ul className="ml-4 list-disc space-y-1 text-xs text-neutral-700">
          <li>
            One-time setup at{" "}
            <a href="/profile" className="underline hover:text-neutral-900">
              /profile
            </a>{" "}
            (basics, handles, master resume upload)
          </li>
          <li>
            Reviewing tailored packages saved from the extension at{" "}
            <code className="rounded bg-neutral-100 px-1">/jobs/[id]/package</code>
          </li>
          <li>
            Optional JobHunt-native discovery at{" "}
            <a href="/search" className="underline hover:text-neutral-900">
              /search
            </a>{" "}
            (Greenhouse / Lever / Ashby + Reddit)
          </li>
        </ul>
        <p className="pt-2 text-[11px] text-neutral-400">
          Need an Anthropic key? Run{" "}
          <code className="rounded bg-neutral-100 px-1">
            python scripts/setup_ai.py
          </code>
          .
        </p>
      </section>
    </main>
  );
}

function BackendStatusBadge({ status }: { status: HealthStatus }) {
  if (status.kind === "loading") {
    return <Badge variant="secondary">Connecting…</Badge>;
  }
  if (status.kind === "error") {
    return <Badge variant="destructive">Offline</Badge>;
  }
  return <Badge>Connected</Badge>;
}

function ProvidersList({ providers }: { providers: ProvidersResponse }) {
  const items: Array<{ label: string; configured: boolean; detail?: string }> =
    [
      { label: "Anthropic Claude", configured: providers.ai_configured },
      {
        label: "Search API (Phase 6)",
        configured: providers.search_provider !== null,
        detail: providers.search_provider ?? undefined,
      },
      {
        label: "GitHub signals",
        configured: providers.github_token_configured,
      },
    ];

  return (
    <div className="space-y-2 border-t border-neutral-100 pt-3">
      <p className="text-xs uppercase tracking-wide text-neutral-500">
        Configured providers (v{providers.version})
      </p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li
            key={item.label}
            className="flex items-center justify-between text-sm"
          >
            <span>
              {item.label}
              {item.detail && (
                <span className="ml-2 text-xs text-neutral-400">
                  {item.detail}
                </span>
              )}
            </span>
            <span
              className={
                item.configured ? "text-emerald-600" : "text-neutral-400"
              }
            >
              {item.configured ? "✓" : "—"}
            </span>
          </li>
        ))}
      </ul>
      <p className="pt-2 text-[11px] text-neutral-400">
        Discovery is keyless — Greenhouse / Lever / Ashby + Reddit. Add
        Brave or Serper key for LinkedIn URL discovery.
      </p>
    </div>
  );
}
