# JobHunt — Architecture

**Status:** Draft v1
**Last updated:** 2026-04-26

This document describes the technical architecture of JobHunt. For *what* we're building and *why*, see PRD.md. For *when* and *in what order*, see Plan.md.

---

## 1. Architectural Principles

Five principles shape every decision below:

**Local-first.** All user data lives on the user's machine. The only outbound traffic is to APIs the user has explicitly configured (Claude, search providers, enrichment). No JobHunt-operated server holds user data.

**BYO-keys.** Every external service requires a user-supplied API key, stored in a local `.env` file. The system never embeds keys.

**Single-tenant.** Designed for one user at a time. No auth system, no multi-tenancy, no role-based access. Drastically simpler.

**Composable AI.** All AI operations follow the meta-prompt pattern (brief → execution) and produce structured JSON outputs. This makes the AI layer debuggable, swappable, and editable by the user.

**Progressive disclosure.** Cheap operations run by default; expensive operations (deep careers-page crawling, full contact discovery) are opt-in per session.

## 2. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       USER (browser)                        │
└─────────────┬─────────────────────────────────┬─────────────┘
              │ HTTPS (localhost)               │ Browser Extension
              │                                 │ (autofill on ATS pages)
┌─────────────▼─────────────────────────────────▼─────────────┐
│                    Next.js Frontend                         │
│       (search UI, feed, fit dashboard, AI panels)           │
└─────────────┬───────────────────────────────────────────────┘
              │ REST + SSE
┌─────────────▼───────────────────────────────────────────────┐
│                   FastAPI Backend                           │
│  ┌────────────┬─────────────┬─────────────┬──────────────┐  │
│  │ Search Svc │ AI Svc      │ Discovery   │ Enrichment   │  │
│  │ (queries,  │ (meta-prompt│ (aggregator,│ (contact     │  │
│  │  diff, idx)│  → exec)    │  posts,     │  discovery)  │  │
│  │            │             │  careers)   │              │  │
│  └────────────┴─────────────┴─────────────┴──────────────┘  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │   Background Worker (BackgroundTasks / Celery)      │    │
│  │   batch searches, watchlist nightly, embeddings     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────┬───────────────────────────────────────────────┘
              │
┌─────────────▼───────────────────────────────────────────────┐
│              Local Storage (single user)                    │
│  ┌───────────────┬───────────────┬───────────────────────┐  │
│  │ SQLite        │ Chroma        │ File store            │  │
│  │ (jobs,        │ (job          │ (resumes, generated   │  │
│  │  contacts,    │  embeddings)  │  cover letters,       │  │
│  │  applications)│               │  briefs, drafts)      │  │
│  └───────────────┴───────────────┴───────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
              │ (outbound only — no inbound APIs)
┌─────────────▼───────────────────────────────────────────────┐
│                    External Services                        │
│  Claude API · JSearch / Adzuna / Jooble · Brave Search /    │
│  Serper · Firecrawl · GitHub API · Twitter/X public ·       │
│  Reddit JSON · Wellfound public                             │
└─────────────────────────────────────────────────────────────┘
```

## 3. Tech Stack

The stack is chosen for solo-developer productivity, AI-friendliness, and minimal moving parts:

**Frontend.** Next.js 15 (App Router) with React 19, TypeScript, Tailwind CSS, shadcn/ui for primitives, Zustand for client state, TanStack Query for server state. Why: fast DX, great component ecosystem, runs locally with `npm run dev`.

**Backend.** Python 3.12 with FastAPI, Pydantic for schemas, SQLAlchemy 2.0 for ORM, Alembic for migrations, `httpx` for outbound HTTP, `structlog` for logging. Why: Python is best-in-class for AI/data work, FastAPI's async story is solid, Pydantic forces structured I/O which matches our AI architecture.

**AI layer.** Anthropic SDK for Python (Claude Sonnet 4.6 default, Opus 4.7 for highest-stakes outputs like senior cover letters). Embeddings via local `sentence-transformers` (free, runs on CPU, no external API dependency). All prompts are versioned files in `prompts/` directory, not hardcoded strings.

**Storage.** SQLite for primary data (zero-config, fully sufficient for single-user scale). Chroma in embedded mode for vector search. Local filesystem for binary artifacts (PDFs, DOCX). PostgreSQL upgrade path documented but not built in v1.

**Background jobs.** FastAPI `BackgroundTasks` for v1 (simple, in-process). Celery + Redis as the upgrade path if user wants reliability across restarts.

**Browser extension.** Manifest V3 Chrome extension (Firefox-compatible). Vanilla JS + light React for sidepanel. Communicates with the local FastAPI backend over `http://localhost:8000`.

**Deployment.** Docker Compose for self-hosting. Three services: `frontend`, `backend`, `worker`. Single `docker compose up` boots the whole system. Local-only by default (binds to `localhost`); optional remote-hosting paths documented in § 12.

## 4. Data Model

The schema is small and intentional. SQLite tables in approximate order of importance:

**`profile`** — single row, the user's persistent profile. Fields: `name`, `headline`, `about_me_text`, `target_seniority`, `work_authorization` (JSON: countries with status), `salary_floor` (INR/USD), `notice_period_days`, `anti_preferences` (JSON), `created_at`, `updated_at`.

**`profile_handles`** — verifiable handle records linked to profile. Fields: `kind` (github / leetcode / kaggle / linkedin / portfolio), `username`, `url`, `last_fetched_at`, `last_signal_json` (cached snapshot of latest signal).

**`resume`** — versioned. Fields: `id`, `version`, `source_file_path`, `parsed_json` (structured experience/skills/education/projects), `is_master` (bool), `derived_from_id` (for tailored versions), `created_at`.

**`search_query`** — saved searches the user runs repeatedly. Fields: `id`, `name`, `role`, `domain`, `locations_json`, `work_mode`, `salary_floor`, `modes_enabled_json`, `last_run_at`.

**`job`** — every job ever ingested. Fields: `id`, `title`, `company`, `company_canonical` (for dedup), `location`, `work_mode`, `salary_text`, `description_md`, `requirements_json` (extracted: skills, years, education, certifications, knockouts), `posted_at`, `apply_url`, `ats_family` (workday / greenhouse / lever / naukri / unknown), `embedding_id`, `first_seen_at`, `last_seen_at`.

**`job_source`** — many-to-one with `job`. Same job can come from multiple sources. Fields: `job_id`, `source_kind` (aggregator / founder_post / careers_page), `source_provider` (jsearch / adzuna / wellfound / company_url), `source_url`, `seen_at`.

**`fit_assessment`** — per (job × profile) computed at ingest. Fields: `job_id`, `skills_match_json`, `experience_verdict`, `domain_match`, `evidence_strength`, `knockout_risks_json`, `verdict` (strong / good / stretch / below / mismatch), `summary_md`, `computed_at`.

**`tailoring_brief`** — Layer 1 output, editable by user before execution. Fields: `id`, `job_id`, `brief_json`, `user_edits_json`, `approved_at`, `executed_at`.

**`tailored_artifact`** — Layer 2 output. Fields: `id`, `brief_id`, `kind` (resume / cover_letter / custom_answers), `content_md`, `output_file_path`, `created_at`.

**`contact`** — discovered contacts per company. Fields: `id`, `company_canonical`, `name`, `role`, `linkedin_url`, `email` (nullable — public emails only), `email_source` (e.g., "company_about_page", "twitter_bio"), `signal_json` (about-them briefing), `discovered_at`, `last_refreshed_at`.

**`outreach_draft`** — Fields: `id`, `contact_id`, `job_id` (nullable), `intent` (referral / application_support / cold_intro), `brief_json`, `draft_text`, `reasoning_text`, `created_at`, `sent_manually_at` (user marks).

**`application`** — what the user submitted. Fields: `id`, `job_id`, `resume_artifact_id`, `cover_letter_artifact_id`, `outreach_draft_id`, `applied_at`, `status` (applied / responded / interview / offer / rejected / ghosted), `notes_md`.

**`watchlist_company`** — Fields: `id`, `name`, `careers_url`, `last_crawled_at`, `last_diff_at`.

**`trust_assessment`** — per-job verdict computed at ingest, refreshed on watchlist re-crawl. Fields: `job_id`, `verdict` (verified / likely_real / suspicious / likely_scam / unknown), `scam_signals_json` (list of detected scam patterns with rule IDs), `ghost_job_signals_json` (list of engagement-farm signals), `positive_signals_json` (list of legitimacy signals), `rationale_md` (one-paragraph human-readable explanation), `static_check_score`, `ai_check_score`, `longitudinal_score`, `computed_at`.

**`job_repost_history`** — supports the longitudinal layer of trust assessment. Fields: `id`, `job_canonical_id` (canonical hash of company + title + description bigrams), `seen_at`, `source_url`, `description_hash`. Each repost creates a new row; the trust subsystem queries this table for repost frequency.

A vector index in Chroma stores embeddings keyed by `job.id` for semantic search.

## 5. Component Architecture

### 5.1 Discovery Layer

Three services, one orchestrator.

**Aggregator client** wraps JSearch, Adzuna, Jooble, TheirStack behind a unified interface. Each provider returns its own schema; an adapter normalizes to the internal `Job` schema. Provider preference and fallback order is configurable per region (India: Adzuna India + JSearch + Jooble; US: JSearch + Adzuna US).

**Founder-post client** queries Twitter/X public, Wellfound, Cutshort, Hasjob, Reddit job-search subreddits, and configured newsletters. Each is a separate adapter. Output is normalized to the same `Job` schema with `source_kind=founder_post` and the original post text preserved as `description_md`. **No LinkedIn.**

**Careers-page crawler** uses Firecrawl (paid, reliable) or a local Playwright fallback to fetch and parse `/careers` pages. Per-domain selectors live in a `careers_selectors.yaml` file that the user (or a one-shot Claude call) extends as new companies are added. The crawler respects `robots.txt` and rate-limits at 1 request per 5 seconds per domain.

**Discovery orchestrator** receives a `SearchQuery`, dispatches to enabled modes in parallel via `asyncio.gather`, applies dedup (canonical company name + role title + Levenshtein on description), writes new jobs to SQLite, queues embeddings.

### 5.2 AI Layer

The meta-prompt pattern is implemented as a small framework. Three abstractions:

**`MetaPrompt`** — produces a structured *brief* from inputs. Each meta-prompt is a versioned Markdown file in `prompts/meta/` with frontmatter declaring inputs, output schema, and target model. Output is JSON, validated by Pydantic.

**`ExecutionPrompt`** — consumes a brief plus inputs and produces the final artifact (resume rewrite, cover letter, outreach draft). Same versioning convention in `prompts/execution/`.

**`StaticPrompt`** — for tasks where strategy doesn't vary (extracting JD requirements, computing skills overlap, parsing resume). These are simpler one-shot calls, also versioned in `prompts/static/`.

Five meta-prompt instances exist:
1. `resume_tailoring_brief` — produces a tailoring brief per job.
2. `outreach_brief` — produces an outreach brief per contact × intent.
3. `cover_letter_brief` — produces a cover-letter strategy brief.
4. `fit_assessment_brief` — produces the multi-dimensional fit verdict (this is also a kind of meta-output even though no execution step follows).
5. `custom_questions_brief` — produces strategies for the 8-10 most common ATS custom questions.

Each meta-prompt encodes domain knowledge from the research. The `resume_tailoring_brief` prompt embeds the four-objective model: parseable formatting, truthful language mirroring, recruiter-search findability, human-skim readability — plus ATS-family detection and knockout-question extraction.

### 5.3 Search & Indexing

**Search service** combines: SQLite full-text on `job.title` + `job.description_md`, Chroma semantic search on the embedding, and structured filters (location, salary, work mode). Results merge with a weighted score (semantic > FTS > recency).

**Indexing service** runs on a background worker. New jobs from Discovery are: deduped, FT-indexed, embedded, fit-assessed against the current profile, and written to the index. End-to-end ~3-8 seconds per job.

**Diff service** powers stateful searches. Each `search_query` row stores `last_run_at`. On re-run, the service surfaces only jobs with `first_seen_at > last_run_at` plus jobs whose fit verdict has improved since (e.g., user added a new GitHub repo that now matches a previously-marginal role).

### 5.4 Enrichment Layer

**LinkedIn URL discoverer** runs Brave Search / Serper queries with site-restricted operators. Returns top-N candidate URLs. The user clicks each URL manually to visit the profile — the system never fetches LinkedIn pages itself. Cost: ~₹0.50 per role.

**Signal aggregator** assembles a "what I learned about this person" briefing from public, non-LinkedIn sources: company About/Team page (Firecrawl), public Twitter/X profile, GitHub if technical, recent news mentions (Brave News), company Crunchbase summary. Output is a one-paragraph briefing stored on `contact.signal_json`.

If a public email is incidentally discovered during signal aggregation (e.g., listed on the company About page, in a Twitter bio, or on a personal website), it's persisted on `contact.email` with a `email_source` field noting where it was found. **There is no separate email-discovery service, no SMTP verification, no pattern inference, and no paid enrichment API.** Public emails only — and many contacts won't have one, which is fine because the primary outreach channel is LinkedIn DM, not cold email.

### 5.5 Browser Extension

Two responsibilities, kept narrow:

**Autofill** — when the user is on a recognized ATS page (URL-based detection: `myworkdayjobs.com`, `boards.greenhouse.io`, `jobs.lever.co`, etc.), the extension calls the local backend `/extension/get-application-package?job_id=X`, receives field mappings, and populates the form. The user reviews and clicks submit.

**Job-save** — on any career-page or job posting, a small popup lets the user save the URL to JobHunt. The backend ingests it as a Mode 3 (careers_page) job.

Communication is `chrome.runtime.sendMessage` → a small content script → `fetch('http://localhost:8000/...')`. CORS is restricted to `localhost`.

### 5.6 Trust Assessment Subsystem

Implements PRD § 3.9. Three layers, each producing a partial score; a final verdict is composed from all three.

**Layer A — Static rules** (`backend/app/trust/rules.py`). A YAML-defined rule set evaluated for every ingested job. Cheap (~50ms per job), deterministic, no AI call. Rule categories:

- **Payment-request rules.** Regex matches for "registration fee," "training fee," "laptop deposit," "security deposit," "background verification fee," "ID card fee," and Indian-language equivalents. Any positive match is a hard scam signal.
- **Contact-channel rules.** WhatsApp/Telegram-only contact mentions, personal-number signatures, missing official email domain.
- **Email-domain rules.** Recruiter email is `gmail.com` / `yahoo.com` / `outlook.com` / `hotmail.com` for a company with a non-trivial web footprint → red flag. Domain typosquatting detection (`infosys-hr.net` for Infosys, `infosy5.com`, etc.) via Levenshtein distance against the canonical company domain.
- **Document-request rules.** Pre-offer Aadhaar/PAN/bank-detail requests, OTP requests, APK download requests.
- **Salary-outlier rules.** Posted salary >2.5x median for the role/seniority/location pulled from a small embedded reference table (top 30 Indian roles + remote roles).
- **MLM-pattern rules.** "Be your own boss," "unlimited earning potential," "build your own team," "passive income," and similar phrase clusters.
- **Indian-specific scam rules.** Naukri "penalty" language, fake government-job claims (anything outside `.gov.in`/`.nic.in` claiming to be a government role), "international placement" with fees.
- **Web-footprint rules.** Company name has zero hits on the company's own domain via Brave Search → suspicious if the listing claims a company with >10 employees.

Each rule has an ID, a severity (info / warning / scam_strong), and contributes to `static_check_score`. The rule library is editable in `backend/app/trust/rules.yaml` so users can extend it without touching code.

**Layer B — AI assessment** (`backend/app/trust/ai_check.py`). A static prompt at `prompts/static/trust_assessment.md` reads the JD + extracted signals + company context and produces a structured verdict with rationale. Single Claude Sonnet call, ~₹0.50-1 per job. The prompt is constrained to:

- Only return `likely_scam` if at least one strong scam signal from Layer A is present, OR if the AI identifies a pattern the rule library missed.
- Default to `unknown` rather than fabricating a verdict on thin evidence.
- Never flag a job as suspicious solely on the basis of company size, sector, or geography.

The AI assessment also generates the human-readable `rationale_md`.

**Layer C — Longitudinal check** (`backend/app/trust/longitudinal.py`). Runs on watchlist re-crawls and on every ingest where the job's canonical hash matches a previous record. Computes:

- **Repost frequency.** Number of distinct ingestion events for the same canonical job (same company + similar title + similar description) in the last 60 days. ≥3 within 60 days = ghost-job warning. ≥6 within 90 days = strong ghost signal.
- **Description churn.** Levenshtein-similarity of the JD against previous reposts. Reposts with near-identical descriptions are stronger ghost signals than reposts with meaningful edits (which may indicate a genuinely repackaged role).
- **Cross-source consistency.** If a job appears on the company's careers page AND on aggregators, that's a positive signal. If it appears on aggregators but NOT on the company's actual careers page, that's a strong scam signal (recruiter posing as the company).

Layer C populates `ghost_job_signals_json`. It runs only when prior data exists; new jobs default to `longitudinal_score = null` and the verdict relies on Layers A and B alone.

**Verdict composition.** A small deterministic function in `backend/app/trust/verdict.py` reads the three scores and produces the final `verdict`:

```
if any scam_strong rule fired → likely_scam
elif AI verdict == likely_scam OR ≥3 warning-severity rules fired → suspicious
elif ≥6 reposts in 90 days OR (≥3 reposts AND >0.95 description similarity) → suspicious (ghost-job-driven)
elif AI verdict == verified AND web-footprint-positive AND no rules fired → verified
elif AI verdict == likely_real AND web-footprint-positive → likely_real
else → unknown
```

Verdicts are recomputed on every job re-ingest so longitudinal signals strengthen over time.

**UX integration.** The frontend renders trust badges only when `verdict ∈ {suspicious, likely_scam}`. `verified` and `likely_real` show no badge — the absence of a warning is the signal. This matches the "warnings-only" UX principle from PRD § 3.9 and Design.md.

## 6. Outreach Drafting Pipeline (Detailed)

The five-stage flow from PRD § 3.6 maps to these technical components:

**Stage 1 — Intent capture.** Frontend modal asks: referral / application_support / cold_intro. Persists on the draft.

**Stage 2 — Context assembly.** Backend collects, in parallel: profile data, job data, contact data (including signal_json), company data (cached). Assembles into a structured input dict.

**Stage 3 — Meta-prompt execution.** `outreach_brief` meta-prompt consumes input, returns a brief with fields: `hook`, `bridge`, `pitch`, `ask`, `tone`, `length_target_words`, `donts_list`. Brief is persisted and returned to UI.

**Stage 4 — Execution prompt.** Frontend shows brief, user optionally edits. On confirm, backend runs `outreach_execution` prompt → returns `draft_text` + `reasoning_text`. Both persisted on `outreach_draft`.

**Stage 5 — Review & manual send.** UI shows brief + draft + reasoning side-by-side. User edits in place, clicks "Copy" or "Open in mail client" (mailto: link). Backend records `sent_manually_at` when user marks done.

## 7. ATS-Awareness Subsystem

A small but important component. Three responsibilities:

**ATS detection** — given a job's `apply_url`, classify the ATS family:
- `myworkdayjobs.com` → Workday
- `boards.greenhouse.io` or `*.greenhouse.io` → Greenhouse
- `jobs.lever.co` or `*.lever.co` → Lever
- `*.icims.com` → iCIMS
- `*.taleo.net` → Taleo
- `*.smartrecruiters.com` → SmartRecruiters
- `*.ashbyhq.com` → Ashby
- `*.naukri.com` → Naukri
- Otherwise → `unknown`

**Knockout-question extraction** — a static prompt that reads the JD and outputs likely knockout questions in structured form: `[{question_text, type: yes_no/years/select, criterion: "min_5_years_python"}]`. The fit assessment surfaces these to the user.

**Custom-question library** — a `prompts/static/custom_questions/` directory of common ATS custom-question prompts ("Why this company," "Why are you leaving," "Tell us about a difficult project," "Salary expectations") with company/role-aware drafts pre-generated when the user clicks "Prepare application."

## 8. External Services & Cost Model

| Service | Purpose | Free tier | Paid pricing | v1 monthly cost (50 apps) |
|---|---|---|---|---|
| Claude API (Sonnet 4.6) | All AI calls | n/a | ~$3/M input tokens | ₹400-1000 |
| JSearch (RapidAPI) | Job aggregation | 150 calls/mo | $10+/mo | ₹0-800 |
| Adzuna API | Job aggregation (India) | Free w/ attribution | n/a | ₹0 |
| Brave Search | LinkedIn URL discovery | 2K calls/mo | $3-5/1000 | ₹0-200 |
| Firecrawl | Careers-page parsing | 500 pages/mo | $16-83/mo | ₹0-1300 |
| sentence-transformers | Embeddings (local, on-device) | Free | n/a | ₹0 |
| GitHub API | Profile signal | 5K req/hr (auth'd) | n/a | ₹0 |

**Total v1 monthly cost at ~50 thoroughly-processed applications: ₹400-3300**, with a typical case around ₹1000-1500. No paid email-enrichment service, no commercial data brokers, no managed embedding API — every external dependency has either a useful free tier or runs fully on-device. This compares to Teal+ at ₹2400/month for a single feature subset.

## 9. Privacy & Security

**Data residency.** All user data lives on the user's machine. Nothing transits to a JobHunt-operated server because no such server exists.

**API keys** are stored in `.env` files with `0600` permissions, never logged, never sent to telemetry (there is no telemetry).

**Outbound traffic** is restricted to the configured external services. No analytics, no error reporting, no usage tracking.

**DPDP compliance (India).** Personal/domestic processing exemption applies. Even so, the system: requires explicit user consent for contact discovery (a per-search confirmation), allows full data export and deletion (`/admin/export`, `/admin/wipe`), and never persists scraped third-party PII beyond what's needed for one outreach session unless the user explicitly saves it.

**No LinkedIn data ingestion.** This is enforced architecturally: there is no LinkedIn adapter in the discovery layer, no LinkedIn scraper in the enrichment layer, and the only LinkedIn-related data the system stores is publicly-Google-indexed URLs.

**Authentication.** None. The backend listens on `localhost` only by default. Optional config flag `BIND_PUBLIC=1` adds basic auth for users who want to access from another device on their LAN.

## 10. Failure Modes & Reliability

The system is designed to fail gracefully because it depends on many external services:

- Each external service has a circuit breaker. Three consecutive failures within 5 minutes pauses calls to that service for 15 minutes.
- Discovery modes are independent. If JSearch is down, Adzuna still runs.
- AI calls retry once on 5xx, fail open with a user-visible error otherwise — never silently produce bad output.
- The local SQLite is the source of truth. External service outages don't lose state, only delay enrichment.
- Background workers are idempotent: re-running an embedding or fit-assessment for an already-processed job is a no-op.

## 11. Extensibility

Three extension surfaces are explicit:

**Discovery adapters.** Each discovery adapter is a class implementing a `discover(query) -> list[Job]` interface. Adding a new source (e.g., a local Indian aggregator) means adding one file in `backend/discovery/adapters/`.

**Prompt overrides.** Every prompt file in `prompts/` can be edited by the user. The system reloads prompts on each request, so iterating on prompts is fast. Users with strong opinions on resume tailoring can fully customize the meta-prompt without touching code.

**Custom-question library.** Adding a new common ATS custom question is a single file in `prompts/static/custom_questions/`.

## 12. Deployment & Hosting

JobHunt is designed to run anywhere Docker runs. Three deployment paths, in order of complexity:

### 12.1 Local-Only (Default, Recommended for v1)

Run on your own laptop or desktop. `docker compose up` and the system is live at `http://localhost:3000`. The backend binds to `localhost` only — there is no network exposure. The browser extension communicates with `localhost:8000`.

This is the recommended v1 path. Cost: ₹0. Security: trivial — nothing leaves the machine. Limitation: only accessible while the host machine is running and on the same device.

### 12.2 Self-Hosted on a VPS (When You Want Phone Access)

When you want JobHunt accessible from a phone, tablet, or another machine, deploy the same Docker Compose stack to a small VPS. Two recommended paths:

**Oracle Cloud Free Tier** offers a 4 vCPU / 24GB RAM ARM Ampere instance free forever — many times more capacity than JobHunt needs. The ARM architecture requires multi-arch Docker images (the official base images we use are arm64-compatible). Pair the deployment with **Cloudflare Tunnel + Cloudflare Access** to expose the app over HTTPS without port forwarding, with email-based access gated to just your address. Cost: ₹0/month indefinitely.

**Hetzner CX22** at approximately ₹400/month (2 vCPU, 4GB RAM, 40GB SSD) is the cheapest reliable paid option. Pair it with **Coolify** (a self-hosted Heroku alternative) for a near-zero-friction deploy: push to GitHub, Coolify rebuilds automatically. Hetzner's EU data centers add ~100-150ms latency to India — fine for a non-realtime application like this.

Either path uses the same Docker Compose file as local. The differences are: setting `BIND_PUBLIC=1` (the backend still doesn't expose itself directly; Cloudflare Tunnel handles ingress), and configuring Cloudflare Access to gate the domain to your email.

### 12.3 Home Server / Always-On Device

If you have an always-on machine at home (Raspberry Pi 5, NUC, repurposed laptop), run Docker Compose there and expose via Cloudflare Tunnel. Same shape as the Oracle Cloud option, but no VPS bill. Cost: ₹0 + electricity.

### 12.4 What's Explicitly Not Recommended

**Vercel + Railway + managed Postgres** would technically work for the frontend, but the architecture is built around single-tenant local SQLite. Splitting into managed services adds cost, complexity, multi-region data residency questions, and platform-specific lock-in for capabilities the system doesn't need. Self-host instead.

**Public deployment without access gating.** Even though the system has no auth (it assumes single-user trust), exposing JobHunt to the public internet without Cloudflare Access (or equivalent) means anyone who discovers the URL can run searches that consume your Claude API budget. Always gate access.

### 12.5 Updates

Whether local or remote, updates are: `git pull && docker compose up --build -d`. Rollback is `git checkout <previous-tag> && docker compose up --build -d`. The user owns the deployment lifecycle entirely.

## 13. Cross-References

- Product scope and behavior: see **PRD.md**
- Build sequence: see **Plan.md**
- Coding rules and AI agent guidance: see **Agent.md**
- UI patterns: see **Design.md**
