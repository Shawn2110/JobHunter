# ADR 0004 — Shipping cuts and deferred work

**Status:** Accepted
**Date:** 2026-05-02
**Tasks:** Cross-phase

## Context

A single working session shipped backend coverage of all 11 phases
(0 through 10) plus the foundational frontend (home, profile,
search, job detail) and a working browser extension scaffold. Some
items from the Plan were intentionally cut to ship the end-to-end
pipeline within the session. This ADR records what was deferred,
why, and how to pick each one up.

## Deferred work

### 1. P3-T1 — sentence-transformers + Chroma vector store

**Shipped:** `HashEmbedder` (deterministic 384-dim character-3-gram
hashing) + in-memory cosine search.

**Why deferred:** sentence-transformers downloads a ~400MB model on
first instantiation; Chroma adds a heavy dep. The Embedder protocol
in `app/indexing/embedder.py` is the swap point — any object with
`dim` and `embed(text)` works. Real semantic retrieval is a clean
substitution when the user wants it.

**Pickup:** add `sentence-transformers` to pyproject, write a
`SentenceTransformersEmbedder(Embedder)` returning the model's vector,
update `default_embedder()` to return it instead of HashEmbedder.

### 2. P4-T4 — DOCX / PDF resume rendering

**Shipped:** `app/services/resume_render.py` produces ATS-safe
single-column Markdown.

**Why deferred:** `python-docx` depends on `lxml`, whose precompiled
Windows DLL is blocked by Application Control on the dev machine.
Markdown render covers the immediate need (download a parseable
representation) without the dep.

**Pickup:** add `python-docx` (or `docxtpl`) on a machine without the
DLL block. Implement `render_resume_docx(resume_json) -> bytes`
following the same single-column / standard-headings constraints
already enforced in the prompt and Markdown renderer. PDF via
LibreOffice headless or `docx2pdf`.

### 3. Frontend pages for tailoring, contacts, outreach, watchlist, applications

**Shipped:** home (`/`), profile (`/profile`), search (`/search`),
job detail (`/jobs/[id]`).

**Why deferred:** the API surface and end-to-end backend pipeline
(prompts → AI → persistence → endpoints) is the harder, more
load-bearing work. Each remaining frontend page is straightforward —
a form + list pattern using the primitives already in
`frontend/components/ui/` and the typed API client in
`frontend/lib/api.ts`. The "Tailor resume / Find contacts /
Draft outreach" buttons in the existing job detail page are
disabled placeholders pointing at the right phases.

**Pickup:** for each, follow the pattern in `frontend/app/profile/page.tsx`:
client component, useEffect-fetch the relevant API, render with the
existing primitives.

### 4. Twitter / Wellfound / Cutshort / Hasjob discovery adapters

**Shipped:** Reddit adapter for Mode 2.

**Why deferred:** Twitter v1 API is paid ($100+/mo) and the v2 free
tier is too thin for keyword search at job-hunt cadence. Wellfound /
Cutshort / Hasjob have no public APIs; reliable extraction would
require browser automation that conflicts with the spirit of
Agent.md's no-LinkedIn-scraping rule (and is fragile against ToS
changes for those sites too). Reddit's public JSON API works at
v1 volumes without any of those concerns. Documented as
PRD § 5 open question 3.

**Pickup:** if the user wants Twitter, add a paid-tier flag to
`.env.example`, implement `adapters/twitter.py` using `tweepy` or
similar. For Wellfound etc., a per-site evaluation: do their
ToS permit personal-use API access? If yes, add the adapter; if no,
leave the gap.

### 5. Firecrawl backend for the careers-page crawler

**Shipped:** plain `httpx` GET that parses JobPosting JSON-LD blocks.
Most modern ATS (Workday, Greenhouse, Lever, Ashby) ship JSON-LD on
first paint, so this covers the common case.

**Why deferred:** Firecrawl is paid; the v1 plain-GET path covers
the bulk of careers pages. SPA-only pages that need Firecrawl /
Playwright remain a follow-up.

**Pickup:** when `FIRECRAWL_API_KEY` is set in `.env`, route the
fetch through `https://api.firecrawl.dev/v1/scrape` instead of the
plain GET. Local Playwright fallback is a separate task.

### 6. Cost dashboard (P10-T2)

**Shipped:** the underlying `ai_call` table with
`input_tokens / output_tokens / cost_usd / duration_ms / succeeded /
prompt_kind / prompt_name / prompt_version` per call. Every AI
service writes a row.

**Why deferred:** purely a frontend rollup over data the backend
already records. Two endpoints + a chart away.

**Pickup:** `GET /admin/costs?since=...` returning grouped rollups,
plus a small page at `frontend/app/admin/costs/page.tsx`.

### 7. Demo seed data (P10-T5)

Not shipped. Low priority — once a user has set up their profile and
run one search, the system has plenty of data to inspect.

## What did ship

- 16 SQLAlchemy models + Alembic migrations applying cleanly.
- 11 prompt files (3 meta, 4 execution, 4 static + custom-question library).
- ~25 service modules across ai/, discovery/, enrichment/, indexing/,
  services/, trust/, workers/.
- 11 API routers wired into FastAPI.
- 134 backend tests passing in ~9s.
- Critical Do-Not-Break tests for: truthfulness check, no LinkedIn
  ingestion, no extension auto-submit, no key leakage in logs,
  localhost-binding default, no auto-hide of trust-flagged jobs,
  no external trust-data sharing.
- Browser extension MV3: manifest, background, content (autofill +
  ATS-family detection), popup. Never submits.
- Frontend foundation: 4 routes + Nav + 5 UI primitives + 3 feed
  components.

## Why this scope was the right cut

The pipeline is the product. Without truthful resume tailoring,
honest fit assessment, scam detection, and structured outreach
drafting the user has nothing useful to do — even the prettiest UI
doesn't help. The remaining UI is mechanical: forms over endpoints
that already exist and are tested. Cutting the UI shipped a
working pipeline; cutting the pipeline would have shipped a
demo with no engine.
