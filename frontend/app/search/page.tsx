"use client";

import { useState, type ChangeEvent, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { searchJobs, type JobOut, type SearchInput } from "@/lib/api";

const EMPTY: SearchInput = {
  role: "",
  domain: null,
  locations: [],
  work_mode: "any",
  salary_floor: null,
  page: 1,
  per_page: 20,
};

export default function SearchPage() {
  const [query, setQuery] = useState<SearchInput>(EMPTY);
  const [locationsRaw, setLocationsRaw] = useState("");
  const [results, setResults] = useState<JobOut[]>([]);
  const [counts, setCounts] = useState<{ new: number; updated: number } | null>(
    null,
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update<K extends keyof SearchInput>(key: K, value: SearchInput[K]) {
    setQuery((q) => ({ ...q, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const locations = locationsRaw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    try {
      const res = await searchJobs({ ...query, locations });
      setResults(res.jobs);
      setCounts({ new: res.new_count, updated: res.updated_count });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-12 gap-6 px-6 py-8">
      {/* Left: search form */}
      <aside className="col-span-12 lg:col-span-4 lg:sticky lg:top-6 lg:self-start">
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border border-neutral-200 bg-white p-5"
        >
          <h2 className="text-lg font-medium">Search</h2>

          <div className="space-y-1.5">
            <Label htmlFor="role">Role</Label>
            <Input
              id="role"
              required
              placeholder="Senior Frontend Engineer"
              value={query.role}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                update("role", e.target.value)
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="locations">Locations (comma-separated)</Label>
            <Input
              id="locations"
              placeholder="Bengaluru, Remote-India"
              value={locationsRaw}
              onChange={(e) => setLocationsRaw(e.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="mode">Work mode</Label>
            <select
              id="mode"
              className="h-9 w-full rounded-md border border-neutral-200 bg-white px-2 text-sm"
              value={query.work_mode ?? "any"}
              onChange={(e) =>
                update("work_mode", e.target.value as SearchInput["work_mode"])
              }
            >
              <option value="any">Any</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">On-site</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="floor">Salary floor</Label>
            <Input
              id="floor"
              type="number"
              placeholder="3500000"
              value={query.salary_floor ?? ""}
              onChange={(e) =>
                update(
                  "salary_floor",
                  e.target.value ? Number(e.target.value) : null,
                )
              }
            />
          </div>

          <Button type="submit" disabled={loading || !query.role}>
            {loading ? "Searching…" : "Run search"}
          </Button>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <p className="text-xs text-neutral-400">
            Mode 1 only (aggregators). Founder posts and careers pages are
            opt-in modes that land in Phase 8.
          </p>
        </form>
      </aside>

      {/* Right: results */}
      <section className="col-span-12 space-y-4 lg:col-span-8">
        {counts && (
          <p className="text-xs text-neutral-500">
            <Badge variant="secondary">{counts.new} new</Badge>{" "}
            <Badge variant="outline">{counts.updated} updated</Badge>
          </p>
        )}

        {results.length === 0 && !loading && counts === null && (
          <p className="text-sm text-neutral-500">
            Run a search to see results.
          </p>
        )}

        {results.length === 0 && counts !== null && (
          <p className="text-sm text-neutral-500">
            No jobs matched. Try broader locations or fewer filters.
          </p>
        )}

        <ul className="space-y-3">
          {results.map((j) => (
            <JobCard key={j.id} job={j} />
          ))}
        </ul>
      </section>
    </main>
  );
}

function JobCard({ job }: { job: JobOut }) {
  return (
    <li className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-medium leading-tight">
            {job.apply_url ? (
              <a
                href={job.apply_url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {job.title}
              </a>
            ) : (
              job.title
            )}
          </h3>
          <p className="text-sm text-neutral-600">{job.company}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
            {job.location && <span>{job.location}</span>}
            {job.work_mode && <span>· {job.work_mode}</span>}
            {job.salary_text && <span>· {job.salary_text}</span>}
            {job.ats_family && <span>· {job.ats_family}</span>}
          </div>
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
