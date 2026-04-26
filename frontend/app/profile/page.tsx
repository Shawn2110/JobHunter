"use client";

import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  fetchProfile,
  uploadResume,
  upsertProfile,
  type HandleKind,
  type Profile,
  type ResumeOut,
} from "@/lib/api";

const HANDLE_KINDS: HandleKind[] = [
  "github",
  "leetcode",
  "kaggle",
  "linkedin",
  "portfolio",
];

const EMPTY_PROFILE: Omit<Profile, "id" | "created_at" | "updated_at"> = {
  name: "",
  headline: null,
  about_me_text: null,
  target_seniority: null,
  work_authorization: null,
  salary_floor: null,
  salary_currency: null,
  notice_period_days: null,
  anti_preferences: null,
  handles: [],
};

export default function ProfilePage() {
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [uploadedResume, setUploadedResume] = useState<ResumeOut | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const p = await fetchProfile();
        if (p) {
          // Strip server-generated fields for editing
          const { id: _id, created_at: _c, updated_at: _u, ...rest } = p;
          void _id;
          void _c;
          void _u;
          setProfile(rest);
        }
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function update<K extends keyof typeof profile>(
    key: K,
    value: (typeof profile)[K],
  ) {
    setProfile((p) => ({ ...p, [key]: value }));
  }

  function addHandle() {
    setProfile((p) => ({
      ...p,
      handles: [...p.handles, { kind: "github", username: "", url: "" }],
    }));
  }

  function updateHandle(idx: number, field: "kind" | "username" | "url", value: string) {
    setProfile((p) => ({
      ...p,
      handles: p.handles.map((h, i) =>
        i === idx ? { ...h, [field]: value } : h,
      ),
    }));
  }

  function removeHandle(idx: number) {
    setProfile((p) => ({
      ...p,
      handles: p.handles.filter((_, i) => i !== idx),
    }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await upsertProfile(profile);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function handleResumeUpload(e: FormEvent) {
    e.preventDefault();
    if (!resumeFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      const out = await uploadResume(resumeFile);
      setUploadedResume(out);
      setResumeFile(null);
    } catch (err) {
      setUploadError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <p className="text-sm text-neutral-500">Loading profile…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl space-y-8 px-6 py-12">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Profile</h1>
        <p className="mt-1 text-sm text-neutral-500">
          One-time setup. Update as life changes. JobHunt fetches your handles
          fresh at search time, so a project pushed yesterday matters more
          than a resume bullet from two years ago.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* ── Basics ─────────────────────────────────────────────── */}
        <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
          <h2 className="text-lg font-medium">Basics</h2>

          <div className="space-y-1.5">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              required
              value={profile.name}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                update("name", e.target.value)
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="headline">Headline</Label>
            <Input
              id="headline"
              placeholder="Backend engineer · Bengaluru · 4 yrs"
              value={profile.headline ?? ""}
              onChange={(e) => update("headline", e.target.value || null)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="seniority">Target seniority</Label>
            <Input
              id="seniority"
              placeholder="senior / staff / mid / fresher"
              value={profile.target_seniority ?? ""}
              onChange={(e) =>
                update("target_seniority", e.target.value || null)
              }
            />
          </div>
        </section>

        {/* ── Handles ────────────────────────────────────────────── */}
        <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium">Verifiable handles</h2>
            <Button type="button" variant="outline" size="sm" onClick={addHandle}>
              + Add handle
            </Button>
          </div>
          <p className="text-xs text-neutral-500">
            URLs only — JobHunt never logs into LinkedIn or fetches profiles
            on your behalf. Handles are used to pull fresh signals at search
            time (GitHub repos, LeetCode rating, etc.).
          </p>

          {profile.handles.length === 0 ? (
            <p className="text-sm text-neutral-400">No handles yet.</p>
          ) : (
            <div className="space-y-3">
              {profile.handles.map((h, idx) => (
                <div
                  key={idx}
                  className="grid grid-cols-12 items-end gap-2"
                >
                  <div className="col-span-3 space-y-1.5">
                    <Label className="text-xs">Kind</Label>
                    <select
                      className="h-9 w-full rounded-md border border-neutral-200 bg-white px-2 text-sm"
                      value={h.kind}
                      onChange={(e) => updateHandle(idx, "kind", e.target.value)}
                    >
                      {HANDLE_KINDS.map((k) => (
                        <option key={k} value={k}>
                          {k}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-3 space-y-1.5">
                    <Label className="text-xs">Username</Label>
                    <Input
                      value={h.username ?? ""}
                      onChange={(e) =>
                        updateHandle(idx, "username", e.target.value)
                      }
                    />
                  </div>
                  <div className="col-span-5 space-y-1.5">
                    <Label className="text-xs">URL</Label>
                    <Input
                      value={h.url}
                      onChange={(e) => updateHandle(idx, "url", e.target.value)}
                      required
                    />
                  </div>
                  <div className="col-span-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeHandle(idx)}
                      title="Remove"
                    >
                      ×
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* ── About me ───────────────────────────────────────────── */}
        <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
          <h2 className="text-lg font-medium">About you</h2>
          <p className="text-xs text-neutral-500">
            Free-text narrative. Captures things resumes don&apos;t — career
            transitions, deal-breakers, motivations. Feeds the meta-prompt&apos;s
            positioning strategy when tailoring resumes.
          </p>
          <Textarea
            rows={6}
            placeholder="Two paragraphs about what you're looking for, what you're done with, and what would make a role a yes…"
            value={profile.about_me_text ?? ""}
            onChange={(e) => update("about_me_text", e.target.value || null)}
          />
        </section>

        {/* ── Compensation & timing ─────────────────────────────── */}
        <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
          <h2 className="text-lg font-medium">Compensation &amp; timing</h2>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="floor">Salary floor</Label>
              <Input
                id="floor"
                type="number"
                placeholder="3500000"
                value={profile.salary_floor ?? ""}
                onChange={(e) =>
                  update(
                    "salary_floor",
                    e.target.value ? Number(e.target.value) : null,
                  )
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ccy">Currency</Label>
              <select
                id="ccy"
                className="h-9 w-full rounded-md border border-neutral-200 bg-white px-2 text-sm"
                value={profile.salary_currency ?? ""}
                onChange={(e) =>
                  update("salary_currency", e.target.value || null)
                }
              >
                <option value="">—</option>
                <option value="INR">INR</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="GBP">GBP</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="notice">Notice (days)</Label>
              <Input
                id="notice"
                type="number"
                placeholder="60"
                value={profile.notice_period_days ?? ""}
                onChange={(e) =>
                  update(
                    "notice_period_days",
                    e.target.value ? Number(e.target.value) : null,
                  )
                }
              />
            </div>
          </div>
        </section>

        {/* ── Save ──────────────────────────────────────────────── */}
        <div className="flex items-center gap-4">
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save profile"}
          </Button>
          {savedAt && (
            <span className="text-sm text-emerald-600">
              ✓ Saved at {savedAt}
            </span>
          )}
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </form>

      {/* ── Resume upload (after profile exists) ──────────────────── */}
      <section className="space-y-4 rounded-lg border border-neutral-200 bg-white p-6">
        <h2 className="text-lg font-medium">Resume</h2>
        <p className="text-xs text-neutral-500">
          Upload a PDF or DOCX. JobHunt parses it once into structured data;
          subsequent searches reference that data, not the raw file. Save
          your profile first.
        </p>

        <form onSubmit={handleResumeUpload} className="flex items-end gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="resume">File</Label>
            <Input
              id="resume"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <Button type="submit" disabled={!resumeFile || uploading}>
            {uploading ? "Parsing…" : "Upload & parse"}
          </Button>
        </form>

        {uploadError && (
          <p className="text-sm text-red-600">{uploadError}</p>
        )}

        {uploadedResume && (
          <div className="rounded-md border border-neutral-200 bg-neutral-50 p-4 text-sm">
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="secondary">v{uploadedResume.version}</Badge>
              <span className="text-neutral-700">{uploadedResume.label}</span>
            </div>
            {uploadedResume.parsed_json && (
              <pre className="max-h-64 overflow-auto rounded bg-white p-3 font-mono text-xs">
                {JSON.stringify(uploadedResume.parsed_json, null, 2)}
              </pre>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
