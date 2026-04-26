"use client";

import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
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

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await fetchHealth();
        const providers = await fetchProviders();
        if (!cancelled) setStatus({ kind: "ok", providers });
      } catch (err) {
        if (!cancelled) {
          setStatus({ kind: "error", message: (err as Error).message });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
          <p className="text-sm text-red-600">
            Backend unreachable: {status.message}. Is the FastAPI server
            running on{" "}
            <code className="rounded bg-neutral-100 px-1">
              {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}
            </code>
            ?
          </p>
        )}
      </section>

      <p className="text-xs text-neutral-400">
        Pre-flight (Phase 0). See{" "}
        <code className="rounded bg-neutral-100 px-1">docs/Plan.md</code> for
        what&apos;s next.
      </p>
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
        label: "Job aggregators",
        configured: providers.aggregators.length > 0,
        detail:
          providers.aggregators.length > 0
            ? providers.aggregators.join(", ")
            : undefined,
      },
      {
        label: "Search API",
        configured: providers.search_provider !== null,
        detail: providers.search_provider ?? undefined,
      },
      {
        label: "Careers crawler",
        configured: providers.crawler === "firecrawl",
        detail: providers.crawler,
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
    </div>
  );
}
