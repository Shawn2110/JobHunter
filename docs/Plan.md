# JobHunt — Execution Plan

**Status:** Draft v1
**Last updated:** 2026-04-26

This document is the persistent execution blueprint for the project. It's written for both the human developer and AI coding agents (Claude Code, Cursor, Aider) to research, scope, and safely execute work.

For the *what*, see PRD.md. For the *how* (technical), see Architecture.md.

---

## 1. How to Read This Plan

Phases run sequentially; tasks within a phase can run in parallel where noted. Each task has: a goal, the files it touches, the test/validation criterion, and the dependencies. AI agents working on this codebase should:

1. Read PRD.md, Architecture.md, and Agent.md before starting any task.
2. Identify which phase and task is currently active by checking the **Current Status** marker below.
3. Confirm the task is unblocked (all `depends-on` tasks complete).
4. Write tests first where possible (the codebase enforces this for backend services).
5. Update the **Current Status** marker on completion and open a follow-up task if scope expanded.

## 2. Current Status

```
Phase: 1 (Profile & Resume Parsing)
Active task: P1-T1 (profile data model + migrations)
Completed:   Phase 0 — P0-T1, P0-T2, P0-T3, P0-T4, P0-T5
Last updated: 2026-04-26
```

This block is the canonical record. Update it after every meaningful checkpoint.

## 3. Risk Register

Live list of known risks; mitigation plans referenced in the relevant tasks.

**R1 — External API instability.** JSearch, Firecrawl, Brave Search can rate-limit or change schemas. *Mitigation:* circuit breakers (Architecture § 10), provider-agnostic adapters, explicit fallback chains.

**R2 — AI cost spiral.** Naive token use can push costs past ₹2000/month. *Mitigation:* two-pass ranking (cheap relevance first, expensive tailoring only on top matches), prompt caching, response logging with token counts.

**R3 — Scope creep into auto-apply.** This is the single biggest design temptation. *Mitigation:* explicit anti-pattern in PRD § 5; coding agents are instructed in Agent.md to refuse any task that adds auto-submission.

**R4 — Resume hallucination.** The execution prompt could fabricate experience if not constrained. *Mitigation:* truthfulness guardrails in the meta-prompt; deterministic post-check that verifies all claimed skills appear in the source resume.

**R5 — DPDP / ToS drift.** Laws and ToS change. *Mitigation:* quarterly review of LinkedIn ToS, DPDP rules, and aggregator API terms — tracked as a recurring task.

**R6 — Single-developer burnout on a 12-week build.** *Mitigation:* phases are sized so each delivers a usable system. Stop after any phase and you have a working tool.

## 4. Phases

```
Phase 0:   Pre-flight                  (Week 1)         Repo, env, secrets, baseline
Phase 1:   Profile & Resume Parsing    (Week 1-2)       User can set up profile
Phase 2:   Discovery — Mode 1          (Week 2-3)       Aggregator search works
Phase 3:   Local Index & Fit           (Week 3-4)       Stateful feed with verdicts
Phase 3.5: Trust Assessment            (Week 4-5)       Scam + ghost-job detection
Phase 4:   Resume Tailoring            (Week 5-7)       Meta-prompt + execution + UI
Phase 5:   Application Packaging       (Week 7-8)       Cover letter, custom Q's, autofill ext
Phase 6:   Contact Discovery           (Week 8-9)       LinkedIn URL + signal (no paid email)
Phase 7:   Outreach Drafting           (Week 9-10)      Five-stage flow
Phase 8:   Discovery — Modes 2 & 3     (Week 10-11)     Founder posts + careers pages
Phase 9:   Watchlist & Diff Mode       (Week 11-12)     Background nightly refresh
Phase 10:  Polish & Hardening          (Week 12-13)     Error handling, docs, deployment guides, demo
```

Stop after Phase 4 and you have a meaningfully better tool than Teal for resume tailoring (with trust filtering Teal lacks entirely). Stop after Phase 7 and you have something no commercial product matches. Phases 8-10 round out the vision.

---

## Phase 0 — Pre-Flight

**Goal:** A repository, dev environment, and secrets management that any AI agent can boot into.

### P0-T1: Repository scaffold
- Files: `frontend/`, `backend/`, `extension/`, `prompts/`, `docs/`, `docker-compose.yml`, `.env.example`, `README.md`, `.gitignore`.
- Validation: `docker compose up --dry-run` succeeds; folder structure matches Architecture.md § 2.
- Depends on: nothing.

### P0-T2: Backend skeleton
- Files: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/models/__init__.py`, `backend/tests/`.
- FastAPI starts on `localhost:8000`, returns `{"status":"ok"}` at `/health`.
- SQLAlchemy connects to SQLite at `data/jobhunt.db`. Alembic initialized.
- `.env` loaded via Pydantic Settings. All required keys validated at startup with clear errors.
- Validation: `pytest backend/tests/test_health.py` passes.
- Depends on: P0-T1.

### P0-T3: Frontend skeleton
- Files: `frontend/package.json`, `frontend/app/layout.tsx`, `frontend/app/page.tsx`, `frontend/components/ui/` (shadcn primitives), `frontend/lib/api.ts`.
- Next.js 15 App Router, TS, Tailwind, shadcn/ui installed and themed.
- Home page renders, hits backend `/health`, displays status.
- Validation: `npm run build` succeeds; visiting localhost:3000 shows a "Backend connected" status.
- Depends on: P0-T2.

### P0-T4: Prompt loading framework
- Files: `prompts/__loader__.md`, `backend/app/ai/prompt_loader.py`, `backend/app/ai/types.py`.
- Loader reads versioned `.md` files with YAML frontmatter (declares: `kind: meta|execution|static`, `inputs`, `output_schema`, `model`).
- Hot-reloads on each call (no caching) so users can edit prompts and see effects immediately.
- Validation: A toy prompt loads, validates, and renders.
- Depends on: P0-T2.

### P0-T5: Anthropic client wrapper
- Files: `backend/app/ai/claude.py`.
- Wraps `anthropic.Anthropic` with: model selection (Sonnet 4.6 / Opus 4.7), JSON-mode helper, retry-on-5xx, token-cost logging to a local SQLite table `ai_calls`.
- Validation: A unit test calls the wrapper with a fixture prompt and asserts a successful structured response.
- Depends on: P0-T4.

---

## Phase 1 — Profile & Resume Parsing

**Goal:** User can install JobHunt, set up their profile, upload a resume, and see it parsed into structured data.

### P1-T1: Profile data model + migrations
- Files: `backend/app/models/profile.py`, Alembic migration.
- Tables: `profile`, `profile_handles` (per Architecture.md § 4).
- Validation: migration applies; tests insert and query a profile.
- Depends on: P0-T2.

### P1-T2: Resume upload + parsing
- Files: `backend/app/services/resume_parser.py`, `backend/app/api/profile.py`.
- POST `/profile/resume` accepts PDF/DOCX, stores file, runs `static/parse_resume.md` static prompt to extract structured JSON (experience, skills, education, projects).
- Validation: upload three real resumes (different formats), assert parser returns clean structured data with no fabricated entries.
- Depends on: P0-T5, P1-T1.

### P1-T3: Profile UI
- Files: `frontend/app/profile/page.tsx`, `frontend/components/profile/*`.
- Wizard: basic info → handles (GitHub, LeetCode, Kaggle, LinkedIn, portfolio) → about-me text → preferences → resume upload → review.
- Each handle is fetched once at save time to verify it resolves; failure shows a warning but allows save.
- Validation: complete the wizard end-to-end, see profile in DB.
- Depends on: P0-T3, P1-T2.

### P1-T4: Handle signal cache
- Files: `backend/app/services/handles.py`.
- For each handle kind, a fetcher returns a small structured "signal" snapshot (e.g., GitHub: top 5 repos with stars, top languages; LeetCode: rating, problems solved by tag). Stored on `profile_handles.last_signal_json`.
- Refreshed on demand and weekly.
- Validation: tests with mocked HTTP for each handle kind.
- Depends on: P1-T1.

---

## Phase 2 — Discovery, Mode 1 (Aggregators)

**Goal:** User submits a search and sees real jobs from JSearch + Adzuna in a unified feed.

### P2-T1: Job data model
- Files: `backend/app/models/job.py`, migration.
- Tables: `job`, `job_source`, `search_query` (per Architecture.md § 4).
- Depends on: P1-T1.

### P2-T2: Aggregator adapters
- Files: `backend/app/discovery/adapters/jsearch.py`, `adapters/adzuna.py`, `adapters/jooble.py`, `adapters/base.py`.
- Each adapter: takes a `SearchQuery`, returns `list[Job]` normalized to internal schema. Mocked HTTP in tests.
- ATS family detection from `apply_url` runs at ingest.
- Validation: contract tests against recorded fixtures from each provider.
- Depends on: P2-T1.

### P2-T3: Discovery orchestrator
- Files: `backend/app/discovery/orchestrator.py`.
- Runs enabled adapters in parallel, dedupes (canonical company name + role title + description Levenshtein), writes to DB.
- Validation: integration test simulating two adapters returning overlapping jobs; final feed has correct dedup.
- Depends on: P2-T2.

### P2-T4: Search UI
- Files: `frontend/app/search/page.tsx`, `frontend/components/search/*`, `frontend/components/feed/*`.
- Search form: role, domain, multi-select locations, work mode, salary, mode toggles (Mode 1 only enabled in this phase).
- Results feed: card per job, source label, title, company, location, posted date.
- Validation: run a real query for "Python backend Bengaluru," see real listings.
- Depends on: P0-T3, P2-T3.

---

## Phase 3 — Local Index & Fit Assessment

**Goal:** Search results show fit verdicts; re-running a search shows only what's new.

### P3-T1: Embeddings & vector index
- Files: `backend/app/indexing/embeddings.py`.
- On job ingest, compute embedding using local `sentence-transformers` (default model: `all-MiniLM-L6-v2`, ~80MB, runs on CPU). Store in Chroma keyed by `job.id`.
- Validation: insert 100 jobs, query semantic search, verify top-K relevance.
- Depends on: P2-T1.

### P3-T2: Fit-assessment meta-prompt
- Files: `prompts/meta/fit_assessment_brief.md`, `backend/app/ai/fit.py`.
- Inputs: profile (resume + handles + about-me), job. Output: structured verdict per Architecture.md § 5.2.
- Verdict includes: skills present/missing, experience verdict, domain match, evidence strength, knockout-question risks, single-word verdict (strong/good/stretch/below/mismatch), ≤3-sentence summary.
- Validation: golden-set tests with curated profile × job pairs and expected verdicts.
- Depends on: P0-T5.

### P3-T3: Knockout extraction (static prompt)
- Files: `prompts/static/extract_knockouts.md`, `backend/app/ai/knockouts.py`.
- Reads JD, outputs structured list of likely knockout questions.
- Validation: 10 real JDs annotated by hand, model output matches ≥80%.
- Depends on: P0-T5.

### P3-T4: Stateful diff
- Files: `backend/app/services/diff.py`, `backend/app/api/search.py`.
- `last_run_at` on `search_query`. Re-running surfaces new jobs and improved-verdict jobs.
- Validation: run search, sleep, ingest a new job, re-run, see only the new job marked "new since last run."
- Depends on: P2-T3, P3-T2.

### P3-T5: Feed UI with verdicts
- Files: `frontend/components/feed/JobCard.tsx`, `frontend/components/feed/FitBadge.tsx`, `frontend/components/feed/JobDetail.tsx`.
- Card shows verdict badge with color coding (strong=green, good=blue, stretch=amber, below=gray, mismatch=red — but include the verdict text, not just color, for accessibility).
- Detail view: full JD, fit dimensions table, knockout flags with explicit "you may need to answer this" warnings.
- Validation: visual review against Design.md spec.
- Depends on: P2-T4, P3-T2, P3-T3.

---

## Phase 3.5 — Trust Assessment

**Goal:** Every ingested job carries a structured trust verdict (verified/likely_real/suspicious/likely_scam/unknown). Suspicious and likely-scam jobs surface warnings in the feed; the system never auto-hides anything. Implements PRD § 3.9 and Architecture § 5.6.

### P3.5-T1: Trust data model
- Files: `backend/app/models/trust.py`, `backend/app/models/job_repost.py`, migration.
- Tables: `trust_assessment`, `job_repost_history` (per Architecture.md § 4).
- Depends on: P2-T1.

### P3.5-T2: Static rules library
- Files: `backend/app/trust/rules.py`, `backend/app/trust/rules.yaml`.
- YAML-defined rule set per Architecture.md § 5.6 Layer A. Categories: payment-request, contact-channel, email-domain, document-request, salary-outlier, MLM-pattern, Indian-specific (Naukri penalty, fake gov-job, international-placement-with-fees), web-footprint.
- Each rule: `id`, `severity` (info / warning / scam_strong), `pattern` (regex or function name), `description`, `applies_to` (locale: india / us / global).
- Validation: 50 hand-curated examples (25 known scams + 25 known legit) — rules correctly classify ≥90%.
- Depends on: P3.5-T1.

### P3.5-T3: AI trust assessment prompt
- Files: `prompts/static/trust_assessment.md`, `backend/app/trust/ai_check.py`.
- Static prompt reads JD + extracted signals (from Layer A) + company context. Output: structured `verdict`, `additional_signals_found`, `rationale_md`.
- Hard constraint in the prompt: only return `likely_scam` if a strong scam signal exists OR a clearly-identified pattern the rule library missed. Default to `unknown` on thin evidence. Never flag based on company size/sector/geography alone.
- Validation: 30 borderline cases (mix of unusual-but-real and sophisticated scams), AI verdict matches human label ≥80%.
- Depends on: P0-T5, P3.5-T2.

### P3.5-T4: Longitudinal repost detection
- Files: `backend/app/trust/longitudinal.py`.
- On every ingest, compute canonical job hash (company + title + description bigrams). Insert into `job_repost_history`. Compute repost frequency over 60/90 day windows. Compute description churn (Levenshtein similarity vs. previous reposts). Compute cross-source consistency (does the same listing appear on the company's actual careers page?).
- Returns structured `ghost_job_signals_json` for the verdict composer.
- Validation: simulate 5 jobs reposted weekly for 8 weeks; assert ghost-job warnings fire at correct thresholds.
- Depends on: P3.5-T1, P2-T3.

### P3.5-T5: Verdict composer
- Files: `backend/app/trust/verdict.py`.
- Deterministic function combining static-check, AI-check, and longitudinal scores into final verdict per the rules in Architecture.md § 5.6.
- Composes `rationale_md` by merging AI rationale with rule citations.
- Pure function, exhaustively tested.
- Depends on: P3.5-T2, P3.5-T3, P3.5-T4.

### P3.5-T6: Trust UI integration
- Files: update `frontend/components/feed/JobCard.tsx`, `frontend/components/feed/JobDetail.tsx`, new `frontend/components/feed/TrustBadge.tsx` and `frontend/components/feed/TrustBreakdown.tsx`.
- Card: badge appears ONLY for `suspicious` (amber) or `likely_scam` (red). Verified/likely_real/unknown verdicts show no badge — the absence is the signal.
- Detail view: when a concern exists, a "Trust check" panel opens showing scam signals, ghost-job signals, positive signals, and the rationale paragraph. User can override (mark as "I trust this") or dismiss.
- Validation: feed of 20 jobs (15 clean, 3 suspicious, 2 scam) renders correctly per Design.md spec.
- Depends on: P3.5-T5, P3-T5.

---

## Phase 4 — Resume Tailoring

**Goal:** User clicks a job, sees a tailoring brief, edits it, generates a tailored resume + cover letter.

### P4-T1: Tailoring meta-prompt
- Files: `prompts/meta/resume_tailoring_brief.md`.
- Encodes the four objectives from PRD § 3.5: parseable formatting (hard constraint), truthful language mirroring, recruiter-search findability, human-skim readability. Branches on detected ATS family.
- Output schema: `positioning`, `vocabulary_shifts`, `keywords_truthfully_supported`, `keywords_to_omit_with_reason`, `emphasis_changes`, `de_emphasis_changes`, `ats_family_specific_notes`, `truthfulness_boundaries`, `knockout_warnings`.
- Validation: golden-set tests on 5 profile × job pairs.
- Depends on: P0-T5, P3-T3.

### P4-T2: Resume execution prompt
- Files: `prompts/execution/resume_rewrite.md`.
- Inputs: tailoring brief (possibly user-edited) + parsed resume. Output: rewritten resume in structured form (same schema as parsed resume) + a diff summary.
- Hard rule: no skill or claim may appear in the output that wasn't in the input. Verified by a deterministic post-check.
- Depends on: P4-T1.

### P4-T3: Truthfulness post-check
- Files: `backend/app/ai/truthfulness_check.py`.
- After execution, compare output skills/companies/titles/dates against input resume. Any new claim → fail with detailed report.
- Validation: feed a deliberately-fabricated output, assert it fails.
- Depends on: P4-T2.

### P4-T4: Resume rendering (DOCX + PDF)
- Files: `backend/app/services/resume_render.py`, `backend/templates/resume_*.docx`.
- Renders structured resume into ATS-safe single-column DOCX (template-based with `python-docx`), then converts to PDF (LibreOffice headless or `docx2pdf`).
- Three templates: `classic` (US-style), `india_fresher` (10th/12th boards, B.Tech), `india_experienced` (LPA, notice period). User picks default in profile.
- Validation: rendered DOCX uploaded to ATS Preview tools (TalentTuner, Resume Worded) parses cleanly.
- Depends on: P4-T2.

### P4-T5: Tailoring UI
- Files: `frontend/app/jobs/[id]/tailor/page.tsx`, `frontend/components/tailor/*`.
- Three-pane layout: original resume left, brief middle (editable JSON form), output right.
- "Generate brief" → "Edit brief" → "Generate resume" → diff view → "Download DOCX/PDF" → "Save as tailored version."
- Validation: end-to-end test from search → tailor → download.
- Depends on: P4-T2, P4-T3, P4-T4, P3-T5.

---

## Phase 5 — Application Packaging

**Goal:** Beyond the resume, JobHunt prepares cover letter + custom-question answers + browser autofill.

### P5-T1: Cover-letter meta + execution prompts
- Files: `prompts/meta/cover_letter_brief.md`, `prompts/execution/cover_letter.md`.
- Brief schema mirrors resume tailoring but for cover-letter strategy (opener angle, narrative arc, closing CTA).
- Length budgets: 200-280 words for most roles.
- Depends on: P4-T1.

### P5-T2: Custom-question answer library
- Files: `prompts/static/custom_questions/*.md` (one per common question), `backend/app/services/custom_questions.py`.
- Pre-generates draft answers for the 8-10 most common ATS custom questions when the user clicks "Prepare application."
- Depends on: P0-T5.

### P5-T3: Application package UI
- Files: `frontend/app/jobs/[id]/package/page.tsx`.
- Single page showing: tailored resume, tailored cover letter, draft custom-question answers, contact info if discovered, application checklist.
- "Open ATS application" button launches the URL in a new tab; the browser extension takes over from there.
- Depends on: P4-T5, P5-T1, P5-T2.

### P5-T4: Browser extension MVP
- Files: `extension/manifest.json`, `extension/background.js`, `extension/content.js`, `extension/popup/*`.
- Detects ATS pages by URL pattern, fetches the latest application package from `localhost:8000`, autofills standard fields (name, email, phone, work history) and pre-filled custom-question answers.
- User reviews each field; system never auto-submits.
- Validation: tested on a real Greenhouse and a real Workday application page.
- Depends on: P5-T3.

---

## Phase 6 — Contact Discovery

**Goal:** For each role, the system surfaces likely contacts with LinkedIn URL + personalization briefing, plus public emails if incidentally found during signal aggregation. **No paid email-finder service** (no Hunter.io, no Apollo) — all signals from public sources only.

### P6-T1: Contact data model
- Files: `backend/app/models/contact.py`, migration.
- Schema includes `email` (nullable) and `email_source` (e.g., "company_about_page", "twitter_bio") for opportunistic public emails. No verification status field — we don't verify.
- Depends on: P1-T1.

### P6-T2: LinkedIn URL discoverer
- Files: `backend/app/enrichment/linkedin_url.py`.
- Brave Search / Serper queries with site-restricted operators. Returns top-N candidate URLs.
- Critically: does not fetch the LinkedIn pages themselves. URL only — the user clicks manually.
- Validation: 10 known companies × known roles, verify ≥80% of expected contacts surface in top 5.
- Depends on: P6-T1.

### P6-T3: Signal aggregator
- Files: `backend/app/enrichment/signal.py`.
- Pulls from public sources only: company About/Team page (Firecrawl), public Twitter/X, GitHub if technical, Brave News, Crunchbase summary.
- During aggregation, opportunistically captures any public email addresses found (e.g., on company About pages, in Twitter bios, on personal sites). Persists on `contact.email` with `email_source` if found; leaves blank otherwise. **No SMTP verification, no pattern inference, no fallback to paid services like Hunter.io or Apollo** — see Agent.md § Hard Refusals.
- Output: a one-paragraph briefing.
- Depends on: P6-T1.

### P6-T4: Contact discovery UI
- Files: `frontend/components/contacts/*`.
- "Find contacts" button on job detail. Returns 3-5 contacts ranked by relevance (Engineering Manager > recruiter > founder for engineering roles, etc.).
- Each contact card: name, role, LinkedIn URL (clickable, opens in new tab — manual visit), public email if found (with the `email_source` shown as attribution, e.g., "found on company About page"), personalization briefing.
- When no email is found, the card simply omits that field — never shows "email unavailable" or similar negative space.
- Depends on: P6-T2, P6-T3, P3-T5.

---

## Phase 7 — Outreach Drafting

**Goal:** User clicks a contact, picks intent, sees brief + draft + reasoning, copies and sends manually.

### P7-T1: Outreach data model
- Files: `backend/app/models/outreach.py`, migration.
- Depends on: P6-T1.

### P7-T2: Outreach meta + execution prompts
- Files: `prompts/meta/outreach_brief.md`, `prompts/execution/outreach_draft.md`.
- Meta-prompt branches on intent (referral / application_support / cold_intro). Output schema per Architecture.md § 6.
- Execution prompt produces draft + reasoning.
- Hard rules in execution: forbidden phrases list ("I hope this finds you well," "leverage," "synergy," etc.); explicit length budget enforced.
- Depends on: P0-T5.

### P7-T3: Outreach UI
- Files: `frontend/app/contacts/[id]/outreach/page.tsx`, `frontend/components/outreach/*`.
- Modal: intent picker → context preview (collapsible) → "Generate brief" → brief editor → "Generate draft" → side-by-side draft + reasoning → "Copy" / "Open mail client" / "Mark sent."
- Depends on: P7-T2, P6-T4.

### P7-T4: "Humanize" pass
- Files: `prompts/execution/humanize.md`.
- Optional second-pass prompt that targets AI-tells specifically (parallel structure, over-formal transitions, hedging language). Run on user click.
- Depends on: P7-T2.

---

## Phase 8 — Discovery, Modes 2 & 3

**Goal:** Founder posts and careers-page crawling join the merged feed.

### P8-T1: Founder-post adapters
- Files: `backend/app/discovery/adapters/twitter.py`, `wellfound.py`, `cutshort.py`, `hasjob.py`, `reddit.py`.
- Each: search by role keywords, parse "we're hiring" patterns, normalize to `Job` schema with `source_kind=founder_post` and original text preserved.
- No LinkedIn adapter, ever.
- Validation: 20 known founder-hiring posts across sources; adapters return ≥70%.
- Depends on: P2-T2.

### P8-T2: Careers-page crawler
- Files: `backend/app/discovery/adapters/careers_page.py`, `backend/app/discovery/selectors.yaml`.
- Firecrawl primary, Playwright fallback. Per-domain selectors in YAML; a one-shot Claude call generates new selectors for unknown domains.
- Respects `robots.txt`, rate-limits 1 req per 5 sec per domain.
- Validation: tested against 10 real Indian and 10 US company careers pages.
- Depends on: P2-T2.

### P8-T3: Mode toggles in search UI
- Files: update `frontend/components/search/*`.
- Modes 2 and 3 toggleable per search; default off (progressive disclosure).
- Depends on: P8-T1, P8-T2, P2-T4.

---

## Phase 9 — Watchlist & Diff Mode

**Goal:** Background nightly refresh of watchlisted companies; new postings queued for the morning.

### P9-T1: Watchlist data model + UI
- Files: `backend/app/models/watchlist.py`, `frontend/app/watchlist/page.tsx`.
- Add/remove companies, set `careers_url`.
- Depends on: P8-T2.

### P9-T2: Background scheduler
- Files: `backend/app/workers/nightly.py`.
- APScheduler runs every night at 03:00 local. Crawls each watchlist company, diffs against index, writes new jobs.
- Validation: trigger manually, confirm new jobs appear with `first_seen_at` timestamps.
- Depends on: P8-T2, P9-T1.

### P9-T3: "New since" indicator
- Files: update `frontend/components/feed/JobCard.tsx`.
- Visual badge for jobs first seen in the last 24 hours.
- Depends on: P3-T4, P9-T2.

---

## Phase 10 — Polish & Hardening

**Goal:** The system is reliable, documented, and demo-able.

### P10-T1: Error handling pass
- Every external service: clear error messages, no silent failures, circuit breakers tested under fault injection.

### P10-T2: Cost dashboard
- Files: `frontend/app/admin/costs/page.tsx`.
- Reads from `ai_calls` table, shows token-cost rollup by day/week/feature.

### P10-T3: Data export & wipe
- Files: `backend/app/api/admin.py`.
- Endpoints to export all user data as a JSON archive and to wipe all data.

### P10-T4: README + setup guide
- Files: `README.md`, `docs/SETUP.md`.
- One-command setup: clone, copy `.env.example`, set keys, `docker compose up`.
- Annotated `.env.example` with where to get each API key and free-tier limits.

### P10-T5: Demo seed data
- Files: `scripts/seed_demo.py`.
- Sample profile + 5 sample jobs + sample tailoring + sample outreach, so a new user can see the full flow without configuring real API keys.

### P10-T6: Deployment guides
- Files: `docs/DEPLOYMENT.md`.
- Document the three deployment paths from Architecture.md § 12: local-only (the default), Oracle Cloud Free Tier with Cloudflare Tunnel, Hetzner + Coolify.
- Each path: step-by-step setup, `.env` configuration specifics, troubleshooting section, rollback instructions.
- Validation: a fresh user with no prior context can follow one path and reach a working deployment within 30 minutes.
- Depends on: P10-T4.

---

## 5. Open Questions (to be resolved during build)

These are deferred decisions, intentionally not nailed down upfront:

1. **Resume rendering library.** `python-docx` + LibreOffice vs. `docxtpl` vs. server-side LaTeX. To be benchmarked in P4-T4.
2. **Embedding model choice.** Default is `sentence-transformers/all-MiniLM-L6-v2` (small, fast, decent quality). May upgrade to `BAAI/bge-small-en-v1.5` if quality matters more than speed. Both are fully local, no external API. Decide during P3-T1 based on retrieval-quality eval.
3. **Twitter/X access.** Public scraping is fragile; the v1 paid tier is $100+/mo. May be worth dropping Twitter from Mode 2 in v1.
4. **Indian aggregator coverage.** JSearch + Adzuna India + Jooble may not be enough. May need to add Foundit and a Naukri JSON-LD scraper. Decide in P2-T2.
5. **Cover letter style for India.** US conventions differ from Indian ones; may need a separate Indian template.
6. **Mobile responsiveness depth.** v1 is desktop-first; phone-readable but not phone-usable. Promote to v2 if user demand emerges.

## 6. Definition of Done (per task)

A task is done when:

1. The implementation matches the goal.
2. Tests pass (unit + integration as applicable).
3. The Current Status block in this file is updated.
4. Architecture.md / PRD.md / Agent.md are updated if the implementation revealed a constraint or decision worth recording.
5. A short note in `docs/decisions/` captures any non-obvious choice (single ADR per decision, max 1 page).

## 7. AI Agent Workflow Reminders

When an AI coding agent (Claude Code, Cursor, etc.) picks up a task:

- Always confirm the active task by reading § 2 of this file.
- Read PRD.md and Agent.md before writing code.
- For any task touching prompts, also read the existing files in `prompts/` to maintain conventions.
- For any task that might cross into anti-patterns (auto-apply, LinkedIn automation, scraping LinkedIn data), refuse and surface the conflict to the user. See Agent.md § "Hard refusals."
- After completing a task, update § 2 and write a one-line entry in `docs/changelog.md`.
