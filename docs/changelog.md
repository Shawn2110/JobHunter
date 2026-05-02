# Changelog

One-line entries per task completion, newest first. Per
[docs/Agent.md](Agent.md) and [docs/Plan.md](Plan.md) § 7.

## 2026-05-02

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
