# Changelog

One-line entries per task completion, newest first. Per
[docs/Agent.md](Agent.md) and [docs/Plan.md](Plan.md) § 7.

## 2026-05-04

- **v2 wave 1 complete: extension is the primary product surface.**
  193 backend tests passing.
- v2 — In-page scoring overlay: extension/content.js auto-mounts on
  supported job pages whenever extracted JD > 200 chars (filters out
  search/landing pages). Initial 'Score this job?' card is opt-in
  (user clicks to spend Anthropic tokens). Full panel shows fit
  verdict + trust badge (only when concerning) + knockouts + Save &
  tailor / Just save / Close actions. SPA-aware re-mount on URL
  change. Coexists with the existing autofill bar.
- v2 — Backend: POST /extension/score (live preview, no persistence)
  + POST /extension/save-and-tailor (persist Job + return package_url).
  Refactor: extracted compute_fit_dict (in app/ai/fit.py) and
  compute_trust_dict (in app/trust/service.py) as stateless helpers
  the persisting wrappers now call. compute_trust_dict skips Layer C
  (longitudinal) since there's no Job row during preview. 7 new tests
  including test_score_does_not_persist_anything which guards the
  no-side-effects contract.
- v2 — Frontend re-framing: Nav.tsx adds 'extension is the main surface'
  pill; app/page.tsx restructured into 3 sections (backend status,
  prominent 'Use the extension' card with install steps, secondary
  'This web app is for' card listing setup + review + optional search
  roles).
- v2 — docs/decisions/0007-v2-wave-1-extension-primary.md: full
  rationale + what's deferred to v2.x.
- **v1.x complete: search-elsewhere panel + rich-payload extension save +
  Apify SPA fallback. 186 backend tests passing.**
- v1.x — Apify SPA fallback: opt-in adapter at
  `backend/app/discovery/adapters/apify.py` for Naukri / Foundit /
  Wellfound. Activates only when `APIFY_API_TOKEN` + the relevant
  per-portal Actor ID is set. Wired into the careers-page dispatcher
  so any watchlist URL on those hosts routes through Apify when
  configured, else dormant. LinkedIn explicitly excluded with two
  new structural guards in `test_no_linkedin.py` (portal detector
  returns None for LinkedIn URLs; Settings has no `linkedin`-named
  fields). 15 tests covering portal detection, parsing, 404 handling,
  config gating, LinkedIn exclusion.
- v1.x — Extension rich-payload save: `extension/content.js` now has
  per-portal SELECTORS for Naukri / Greenhouse / Lever / Ashby /
  Foundit / Wellfound / Workday with generic h1/title/main fallbacks.
  `extractJobFromPage()` returns `{portal, title, company, location,
  description_md, apply_url}`. Popup asks the active tab's content
  script for the rich payload; falls back to URL+title if the script
  didn't inject. Backend `/extension/save-job` accepts both shapes,
  dedups on `apply_url`, records portal in `source_provider`. 5 new
  API tests.
- v1.x — Search-elsewhere panel: `frontend/lib/external_search.ts`
  + new section in the `/search` form. 7 portal buttons (LinkedIn,
  Naukri, Indeed, Foundit, Wellfound, Glassdoor, HN Who's Hiring)
  open native search in a new tab using user's logged-in browser
  session. Pure URL templates; zero JobHunt-side fetches.
- **v1 wave 2 complete: end-to-end tailoring loop is live.** 164 backend
  tests passing.
- Schema change: `tailoring_brief.kind` discriminator + nullable
  `tailored_artifact.brief_id` + direct `tailored_artifact.job_id` so
  cover-letter and custom-question artifacts can persist without a
  resume-tailoring brief. SQLite migration via raw RENAME / CREATE
  TABLE / INSERT-SELECT (batch_alter_table can't do nullability changes
  cleanly when the FK was auto-named).
- `services/cover_letter.py`: one-shot Layer-1 brief → Layer-2
  execution. Persists `TailoringBrief(kind="cover_letter")` plus
  `TailoredArtifact(kind="cover_letter")` with body in `content_md`.
- API endpoints:
  • `POST /tailoring/jobs/{id}/cover-letter` — one-shot
  • `POST /tailoring/jobs/{id}/custom-questions` — runs all 5 (or a
    subset via `{"keys": [...]}`)
  • `GET /tailoring/jobs/{id}/artifacts` — list any-kind artifacts
- `frontend/app/jobs/[id]/package/page.tsx`: three-section page
  (resume / cover letter / custom answers) with generate / regenerate /
  copy buttons, truthfulness-violation warning panel for resumes,
  collapsible brief + reasoning views, deep-link to ATS apply URL.
- `frontend/app/jobs/[id]/page.tsx`: enables the previously-disabled
  "Tailor resume" button — now links to the package page.
- `docs/decisions/0006-v1-v2-product-split.md`: documents the
  architectural split — v1 = web app + thin extension, v2 = extension
  as primary surface. Apify add-on for non-LinkedIn SPAs scoped to
  v1.x, not v1 wave 2.

## 2026-05-02

- **Discovery rebased to keyless ATS adapters.** 156 backend tests passing.
  Removed JSearch / Adzuna / Jooble / TheirStack adapters + their
  settings + `.env.example` entries entirely (see ADR 0005). Added
  `discovery/ats_providers.py` (URL → provider+slug detector) and three
  new keyless adapters: `adapters/greenhouse.py`,
  `adapters/lever.py`, `adapters/ashby.py`. CareersPageAdapter
  rewritten as a dispatcher (Greenhouse / Lever / Ashby URLs → board
  API; everything else → JSON-LD parsing fallback). WatchlistCompany
  gains `ats_provider` + `ats_slug` columns autodetected on insert.
  `scripts/setup_ai.py` is now the recommended setup path — single
  required key (Anthropic). Naukri / Foundit / Wellfound documented as
  Playwright-path follow-ups, not shipped.
- **Backend pipeline complete across all 11 phases. 134 backend tests passing.**
  Deferred surface documented in docs/decisions/0004-shipping-cuts-and-deferred-work.md.
- P10 — Polish: /admin/export (every user-data table → JSON),
  /admin/wipe (typed "WIPE" confirmation, deletes rows + binary
  artifacts under data/). Critical Do-Not-Break tests:
  test_keys_never_logged.py (greps log capture for sensitive
  substrings + asserts /providers returns no long strings),
  test_localhost_only.py (Settings binds to 127.0.0.1 by default,
  0.0.0.0 only when BIND_PUBLIC=1). docs/SETUP.md +
  docs/DEPLOYMENT.md (3 paths: local-only, Oracle Free Tier +
  Cloudflare Tunnel + Access, Hetzner + Coolify) +
  docs/decisions/0004-shipping-cuts-and-deferred-work.md.
- P9 — Watchlist + nightly scheduler: WatchlistCompany model,
  APScheduler AsyncIOScheduler firing crawl_watchlist at 03:00 local,
  /watchlist endpoints + /watchlist/run-now manual trigger, worker
  runner for the docker-compose 'worker' service.
- P8 — Discovery Modes 2 + 3: RedditAdapter (public JSON API, hiring-
  post filter), CareersPageAdapter (httpx + JobPosting JSON-LD,
  per-domain rate limit at 1 req / 5s), selectors.yaml for fallback
  CSS selectors, adapters_for_modes() router on the orchestrator.
- P7 — Outreach drafting: OutreachDraft model, prompts/meta/
  outreach_brief.md (intent-branched: referral / application_support /
  cold_intro), prompts/execution/outreach_draft.md (no greeting, no
  signature, hard-enforced forbidden phrases), prompts/execution/
  humanize.md (optional AI-tells removal pass), full /outreach API
  including mark-sent for the user's manual-send signal.
- P6 — Contact discovery: Contact model (no verified-email field —
  emails are opportunistic-only with email_source labels),
  enrichment/linkedin_url.py (Brave preferred, Serper fallback,
  site:linkedin.com/in URLs only — never fetches LinkedIn),
  enrichment/signal.py (public-page aggregation + email extraction),
  /contacts/discover. Critical test_no_linkedin.py asserts no
  LinkedIn page fetches anywhere in backend + no linkedin*.py adapter
  file exists.
- P5 — Application packaging: cover-letter meta + execution prompts
  (forbidden-phrase enforcement), 5 custom-question prompts
  (why_this_company / why_this_role / why_leaving / biggest_project /
  salary_expectations), services/custom_questions.py dispatcher,
  Browser Extension MV3 (manifest, background, content with autofill +
  no-submit guard, popup with save-job + open-app), /extension API
  for application-package + save-job. Critical
  test_no_autosubmit.py greps for any submit-trigger pattern in the
  extension JS (after stripping comments) and asserts only
  localhost:8000 / 127.0.0.1:8000 are reachable.
- **Phase 4 backend complete** (T4 DOCX render + T5 frontend UI deferred).
  Active task: P5-T1. 119 backend tests passing.
- P4 — Resume tailoring: Layer-1 meta-prompt + Layer-2 execution prompt
  + truthfulness post-check + tailoring service + API endpoints
  (POST /tailoring/jobs/{id}/brief, PUT briefs/{id}/edits,
  POST briefs/{id}/execute). Critical test_truthfulness_check.py asserts
  fabrication detection works (companies, titles, dates, education,
  skills) — 8 tests. Markdown render lands; full DOCX/PDF deferred
  because python-docx (lxml) is blocked by Application Control locally.
- **Phase 3.5 complete.** Active task: P4-T1 (tailoring meta-prompt). 111
  backend tests passing.
- P3.5-T6 — Trust UI integration: TrustBadge (renders only for
  suspicious / likely_scam), TrustBreakdown panel on /jobs/[id], badge
  inline on JobCard. Backend search endpoints refresh trust_assessment
  for serialization. Critical Do-Not-Break tests:
  test_no_auto_hide.py asserts /search and /jobs include likely_scam
  rows; test_no_external_trust_share.py greps backend source for any
  trust-data exfiltration pattern.
- P3.5-T5 — Verdict composer: pure deterministic combiner per
  Architecture § 5.6 decision tree. 8 tests across all branches.
- P3.5-T4 — Longitudinal repost detection: canonical_job_id (company +
  title + bigram fingerprint), record_sighting + evaluate_longitudinal
  with 60/90-day windows. 5 tests.
- P3.5-T3 — AI trust assessment prompt + service: hard constraints in
  the prompt (only return likely_scam with strong rule hit OR clear
  novel pattern; never flag based on size/sector/geography; default to
  unknown on thin evidence).
- P3.5-T2 — Static rules library: rules.yaml with 21 categorized
  patterns + rules.py loader/runner with score composition. 8 tests.
- P3.5-T1 — TrustAssessment + JobRepostHistory models + migration.

## 2026-04-28

- **Phase 3 complete.** Active task: P3.5-T1 (trust data model). 90 backend
  tests passing.
- P3-T5 — Feed UI with verdicts: FitBadge (5 color-paired-with-text
  verdicts per Design.md § 5.2), JobCard extracted to
  components/feed/, /jobs/[id] detail page (3-column: summary +
  description + actions), knockout pills on cards.
- P3-T4 — Stateful diff: services/diff.py + saved-search endpoints
  (POST /search/saved, GET /search/saved, POST /search/saved/{id}/run).
  First run treats all jobs as new; subsequent runs use first_seen_at
  windowing against last_run_at. 2 tests.
- P3-T3 — Knockout extraction: prompts/static/extract_knockouts.md
  (8 category hints, conservative on soft skills) + ai/knockouts.py.
  2 tests.
- P3-T2 — Fit assessment: FitAssessment model + migration,
  prompts/meta/fit_assessment_brief.md (honesty-over-flattery: flags
  stretch/below verdicts and surfaces knockouts), ai/fit.py with
  upsert-on-job_id. 2 tests.
- P3-T1 — Indexing: HashEmbedder (384-dim character-3-gram, NOT
  semantic — placeholder until sentence-transformers is wired in),
  index/service.py with embed_job/reindex_pending/search_similar,
  Job.embedding_vector column + migration. 8 tests.

## 2026-04-26

- **Phase 2 complete.** Active task: P3-T1 (embeddings + vector index). 72
  backend tests passing.
- P2-T4 — Search UI: `/search` page (sticky form left, results right) + Nav
  in root layout. JobCards render title, location/mode/salary/ATS chips,
  source provider badges.
- P2-T3 — Discovery orchestrator + dedupe: `run_discovery` runs adapters
  in parallel, dedupes within batch, then matches against existing DB rows
  via canonical_company + normalized_title + description Levenshtein. ATS
  family detected from apply URL. POST /search, GET /jobs, GET /jobs/{id}
  endpoints. 23 tests.
- P2-T2 — Aggregator adapters: JSearch, Adzuna, Jooble + base
  DiscoveryAdapter ABC. Each adapter self-skips when not configured;
  errors are caught and logged without breaking the orchestrator.
- P2-T1 — Job, JobSource, SearchQuery models + migration.
- **Phase 1 complete.** Active task: P2-T1 (job data model). 41 backend tests
  passing.
- P1-T4 — Handle signal cache: `app/services/handles.py` with per-kind
  fetchers (GitHub REST, LeetCode GraphQL, Kaggle URL verify, LinkedIn
  stub, portfolio HEAD), `refresh_handle()` dispatcher, and POST
  `/profile/handles/{id}/refresh` endpoint. 6 tests including a
  no-LinkedIn-requests guard.
- P1-T3 — Profile UI: `/profile` page with full-form editor (basics,
  handles, about-me, compensation), Button/Input/Textarea/Label primitives,
  and resume upload form that surfaces parsed JSON inline.
- P1-T2 — Resume upload + parsing: `Resume` model + migration,
  `prompts/static/parse_resume.md` (strict JSON schema, no fabrication),
  `app/services/resume_parser.py` (PDF + DOCX extraction via pypdf +
  docx2txt), `POST /profile/resume` endpoint. 5 service tests + 5 API tests.
- P1-T1 — Profile data model: `Profile` + `ProfileHandle` SQLAlchemy
  models, Alembic migration, 4 model tests (insert, relationship, unique
  constraint, cascade delete).
- **Phase 0 complete.** Active task: P1-T1 (profile data model + migrations).
- P0-T5 — Claude wrapper: `ClaudeClient` with model selection (Sonnet 4.6
  default, Opus 4.7 high-stakes), `complete()` and `complete_json()`
  methods, retry-on-5xx via SDK, USD cost estimation, and per-call
  logging to the `ai_call` table. First Alembic migration applies
  cleanly. `frozen_claude` fixture in `conftest.py` enables AI-using
  service tests without hitting the live API. 9 new tests, 21 total.
- P0-T4 — Prompt loading framework: `PromptLoader` reads versioned `.md`
  files with YAML frontmatter, validates against `PromptManifest`,
  substitutes `{{ var_name }}` placeholders, and validates AI responses
  against `output_schema` (string passthrough or JSON Schema). Hot-reloads
  on every call. `prompts/static/echo.md` is the smoke-test prompt.
  10 new tests, 12 total.
- P0-T3 — Frontend skeleton: Next.js 15 App Router + React 19 + Tailwind 3
  + shadcn-style Badge primitive. Home page hits `/health` and `/providers`,
  shows backend status and configured-provider checklist. `npm run build`
  passes.
- P0-T2 — Backend skeleton: FastAPI app with structlog, SQLAlchemy 2 async
  engine, Alembic init, Pydantic Settings auto-detecting which providers
  are configured. `/health` and `/providers` endpoints. `pytest` (2 tests)
  passes.
- P0-T1 — Repository scaffold: folders, `.env.example`, `.gitignore`,
  `README.md`, `docker-compose.yml`, `prompts/__loader__.md`,
  `docs/changelog.md`, `docs/decisions/`.
