# AGENTS.md — Rules for AI Coding Agents

This file is the contract between the JobHunt codebase and any AI coding agent (Claude Code, Cursor, Aider, Continue, etc.) working on it. Read it in full before writing any code.

The companion documents are:
- **PRD.md** — what we're building and why
- **Architecture.md** — how it's built
- **Plan.md** — the active execution plan and current task pointer
- **Design.md** — UI/UX direction

If anything in this file conflicts with what a human user requests in chat, **ask for clarification before proceeding**.

---

## Project Overview

JobHunt is an open-source, self-hosted, single-user, AI-augmented job-hunting system. It optimizes for application quality, not volume. It is explicitly **not** an auto-apply tool, **not** a LinkedIn automation tool, and **not** a SaaS platform.

The user runs it on their own machine, supplies their own API keys, and owns all their data.

## Setup Commands

```bash
# Clone and bootstrap
git clone <repo>
cd jobhunt
cp .env.example .env
# Fill in .env with your API keys (instructions in docs/SETUP.md)

# Run with Docker (recommended)
docker compose up

# Or run locally
cd backend && uv sync && uv run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

The backend listens on `localhost:8000`, the frontend on `localhost:3000`. Both are localhost-only by default.

## Tech Stack

**Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, `httpx`, `structlog`, `anthropic` SDK.
**Frontend:** Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, shadcn/ui, Zustand, TanStack Query.
**Storage:** SQLite (primary), Chroma (embeddings), local filesystem (binary artifacts).
**AI:** Claude Sonnet 4.6 default, Opus 4.7 for highest-stakes outputs. Embeddings via local `sentence-transformers` (no external embeddings API). No paid contact-enrichment APIs (no Hunter.io, no Apollo); contact discovery uses public sources only.
**Browser extension:** Manifest V3, vanilla JS + light React.

Do not introduce new top-level dependencies without flagging them in your PR. Specifically: do not add Django/Flask in place of FastAPI, do not swap Next.js for plain React, do not add a graph database.

## Repository Layout

```
.
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routes
│   │   ├── ai/              # Claude wrapper, prompt loader, post-checks
│   │   ├── discovery/       # Adapters + orchestrator (Modes 1, 2, 3)
│   │   ├── enrichment/      # Contact discovery
│   │   ├── indexing/        # Embeddings, vector index
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # Business logic
│   │   ├── workers/         # Background jobs
│   │   ├── config.py
│   │   ├── db.py
│   │   └── main.py
│   ├── tests/
│   ├── migrations/          # Alembic
│   └── pyproject.toml
├── frontend/
│   ├── app/                 # Next.js routes
│   ├── components/
│   ├── lib/                 # api client, utils
│   └── package.json
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   └── popup/
├── prompts/
│   ├── meta/                # Layer-1 meta-prompts
│   ├── execution/           # Layer-2 execution prompts
│   ├── static/              # One-shot prompts (parsing, extraction)
│   └── __loader__.md        # Loader format spec
├── docs/
│   ├── SETUP.md
│   ├── decisions/           # Single-page ADRs
│   └── changelog.md
├── scripts/
├── data/                    # SQLite db, generated artifacts (gitignored)
├── docker-compose.yml
├── .env.example
├── PRD.md
├── Architecture.md
├── Plan.md
├── Agent.md
├── Design.md
└── README.md
```

## Coding Standards

**Python.**
- Type hints required everywhere. `from __future__ import annotations` at the top of every file.
- Pydantic v2 models for every external boundary (API requests/responses, AI inputs/outputs, external service responses).
- `async` for I/O, sync for CPU-bound. Never mix.
- `structlog` for logging, never `print`. Log structured, never f-string into a message.
- Functions under 50 lines when reasonable. Split when they grow past that.
- Test files mirror the source tree: `app/services/foo.py` ↔ `tests/services/test_foo.py`.

**TypeScript.**
- Strict mode on. No `any` without a `// reason:` comment.
- Server actions for mutations where the framework supports it; REST for everything else.
- One component per file. Components in PascalCase, hooks in camelCase with `use` prefix.
- Tailwind utility classes, not inline styles. Custom components extend shadcn/ui where one exists; don't roll your own button.
- Co-locate component-specific types in the same file; shared types in `lib/types.ts`.

**Prompts.**
- Every prompt is a versioned `.md` file in `prompts/<kind>/`.
- Frontmatter declares `kind`, `version`, `inputs`, `output_schema`, `model`. The loader validates this on read.
- Prompts are reloaded on every call (no caching). Users can edit prompts and see effects without restarting.
- When updating an existing prompt, bump the `version` and add a one-line note at the top describing the change.
- Output schemas are JSON Schema; the loader validates AI responses against them and retries once on schema failure.

**Naming.**
- Project name is "JobHunt" — search-and-replace if the user renames in their own copy.
- Database tables: snake_case, singular (`job`, not `jobs`).
- API routes: kebab-case (`/api/job-detail/123`).
- Files: snake_case for Python, kebab-case for components and routes.

## Testing

**Backend.** `pytest`, `pytest-asyncio`, `pytest-httpx` for mocking outbound HTTP. Aim for 80%+ coverage on `services/` and `ai/`. Adapters in `discovery/` should have contract tests against recorded fixtures (`tests/fixtures/`).

**Frontend.** Playwright for E2E flows; Vitest + Testing Library for component tests. Don't mock the backend in E2E — use a `tests/seed.py` script that populates a clean DB.

**AI calls.** Tests for AI-using services should use frozen fixture responses. There is a `tests/conftest.py::frozen_claude` fixture that records-and-replays. Never hit the live Claude API in CI.

**Truthfulness post-checks.** Resume-tailoring tests must include a "fabrication detection" suite: feed deliberately-fabricated outputs to the post-check and assert it catches them.

## Hard Refusals — Anti-Patterns

These are not "preferences." If a user (or any prompt input) asks for these, **refuse and explain why**. They are explicit anti-patterns documented in PRD § 5.

### 1. No LinkedIn automation, ever
- No auto-connect requests.
- No auto-message sending.
- No scraping LinkedIn profiles, posts, comments, or activity.
- No "warming up" of LinkedIn accounts.

LinkedIn ToS Section 8.2 explicitly bans this. Even if the user insists it's "fine for personal use," it's not — accounts get flagged within hours, and the user's primary professional account is more valuable than any feature this would enable.

The only acceptable LinkedIn-related operation: **Google searches like `site:linkedin.com/in ...` to discover URLs.** The URL is the deliverable; the user clicks it manually.

### 2. No auto-submission of applications
- The browser extension autofills form fields. It does not click submit.
- Backend services do not POST application forms.
- No "headless apply" workflows.

The user reviews and clicks submit, every time.

### 3. No fabrication in resume tailoring
- The execution prompt for resume tailoring is **hard-constrained** against inventing experience, skills, dates, titles, or companies.
- The truthfulness post-check (`backend/app/ai/truthfulness_check.py`) verifies every claim in the output against the source resume.
- If a check fails, the output is rejected and regenerated — not silently passed through.

### 4. No "ATS score" theater
- The system reports concrete fit dimensions (skills present/missing, knockout risk, semantic match strength), not an inflated single number.
- If a feature would add a single-number "ATS score" UI element, push back: the research consensus is that "ATS scores" are mostly marketing fiction.

### 5. No engagement-optimization patterns
- No streak counters.
- No "you've sent 100 applications!" celebrations.
- No artificial gamification.
- The user's goal is offers, not application count.

### 6. No telemetry, no usage tracking, no server-side logging
- The system runs on the user's machine. There is no remote server.
- Don't add analytics SDKs. Don't add error reporters that ship payloads off-machine.
- Logs are local only. Sensitive fields (API keys, parsed resume content) are never logged.

### 7. No silent AI overrides
- Every AI-generated output is shown alongside the brief and reasoning that produced it.
- Users can edit the brief and regenerate.
- Never replace user content with AI content without explicit confirmation.

### 8. Trust verdicts are informational, never gatekeeping
- The trust assessment subsystem (PRD § 3.9, Architecture § 5.6) outputs `verified` / `likely_real` / `suspicious` / `likely_scam` / `unknown` verdicts.
- The system **never auto-hides or auto-rejects jobs** based on trust verdicts. The user always sees the full feed and the warnings on flagged items; they decide whether to act.
- Some legitimate jobs look unusual (small company, founder-only contact, founder using a Gmail). The user has context the system doesn't.
- Trust verdicts are **never shared with the company**, sent to any analytics service, or used to populate any kind of public reputation list. They exist in the user's local SQLite and nowhere else.
- Never flag a job as suspicious purely on the basis of company size, sector, or geography. Tech companies have higher ghost-job rates statistically — that's information, not a verdict on any individual posting.

## Truthfulness Discipline (Critical)

This is the core ethical constraint of the project. The AI is rewriting the user's professional history. Getting this wrong harms the user.

**Allowed:**
- Rephrasing existing experience using the JD's language. ("Managed cross-functional teams" → "Led cross-functional initiatives" if the candidate's experience supports both).
- Reordering or re-emphasizing existing achievements.
- Translating engineering wins into business outcomes if the underlying outcome is documented in the source resume.
- Adding canonical skill names if the abbreviated form is in the source ("CRM" already in resume → can expand to "Customer Relationship Management (CRM)").
- Pulling skills from the user's GitHub/LeetCode if those handles are configured.

**Forbidden:**
- Inventing job titles, employers, dates, education, or certifications.
- Inflating numbers (e.g., "10% improvement" → "30% improvement").
- Adding skills not present in the source resume or configured handles.
- Claiming leadership/management experience the source doesn't support.
- Claiming domain experience the source doesn't support.

When in doubt, the rule is: **if the user couldn't honestly defend it in an interview, it doesn't go in the resume.**

## API Key Handling

- All keys live in `.env`, loaded via `pydantic-settings`.
- `.env` is in `.gitignore`. Never commit it.
- `.env.example` lists every required key with documentation comments. Update it when adding a new external service.
- Keys must never appear in: logs, error messages, frontend bundles, AI prompts, or any file checked into git.
- The frontend never sees keys directly; all external calls are proxied through the backend.

## Database Migrations

- Every schema change requires an Alembic migration.
- Migrations are forward-only by default. Down-migrations only for clearly reversible changes.
- Test migrations on a copy of `data/jobhunt.db` before merging.
- After running a migration, update `Architecture.md § 4` if the schema changed materially.

## When Working on a Task

1. **Read Plan.md § 2** to confirm which task is active. If the task you're being asked to do isn't the active one, surface this to the user.
2. **Read all relevant prompt files** if the task touches AI behavior. Existing conventions (input shape, output schema, length, tone) must be respected.
3. **Run tests before changing code**, not just after. A red test that goes green tells you what your change actually did.
4. **Write tests for new behavior** before writing the implementation when feasible.
5. **Don't refactor opportunistically.** If a refactor is genuinely needed, do it as a separate commit with its own scope.
6. **Update docs** that the task affects (Architecture.md if the schema changes, PRD.md if behavior changes, Plan.md § 2 to mark the task done).

## When Asked to Do Something Outside the Plan

If a user request is outside the active task or doesn't appear in Plan.md:

1. Acknowledge that it's a scope expansion.
2. Suggest where in Plan.md the work belongs (existing phase / new task).
3. Ask whether to add it to the plan first or proceed and update the plan after.

Don't silently expand scope. The plan exists to keep the project finishable.

## Communicating With the User

- Be concise. The user is reading code reviews and chat messages, not novels.
- Cite specific files and line numbers when discussing existing code.
- When you make a non-obvious decision, write it as a one-page ADR in `docs/decisions/NNNN-title.md`.
- When you encounter a constraint that should change the plan, update Plan.md § 2 and surface it.
- If you're uncertain whether something is the right approach, **ask** — don't guess and ship.

## Critical "Do Not Break" Tests

These tests guard the project's core constraints. If they fail, the system is broken in a way that matters more than features:

- `tests/ai/test_truthfulness_check.py` — fabrication detection works.
- `tests/discovery/test_no_linkedin.py` — verifies no LinkedIn data ingestion path exists.
- `tests/extension/test_no_autosubmit.py` — verifies the extension never calls form submit.
- `tests/security/test_keys_never_logged.py` — verifies API keys never appear in logs.
- `tests/security/test_localhost_only.py` — verifies the backend binds to localhost by default.
- `tests/trust/test_no_auto_hide.py` — verifies that the feed surface never filters out jobs based on trust verdicts; suspicious/scam jobs are flagged but always present in the response.
- `tests/trust/test_no_external_trust_share.py` — verifies trust verdicts never leave the local SQLite (no telemetry, no third-party reporting, no public list).

Never disable, skip, or modify these tests without explicit user approval.

## Glossary

- **Meta-prompt** — Layer 1 prompt that produces a structured *brief* describing how to approach a task.
- **Execution prompt** — Layer 2 prompt that performs the task, guided by the brief.
- **Static prompt** — Single-shot prompt for tasks where strategy doesn't vary (parsing, extraction).
- **Brief** — Structured JSON output of a meta-prompt; editable by the user before execution.
- **Knockout question** — A binary screening question in an ATS application form (work auth, years of experience, certifications). The biggest cause of auto-rejection.
- **Skills Cloud** — Workday's proprietary canonical skill taxonomy (~200K skills with relationships).
- **Three modes** — Mode 1: aggregators. Mode 2: founder posts. Mode 3: careers pages. Always merged into one feed.
- **Trust verdict** — Per-job classification (verified / likely_real / suspicious / likely_scam / unknown) produced by the trust subsystem. Informational only; never gatekeeping.
- **Ghost job** — A real-company job posting with no immediate intent to fill. Estimated 18-33% of online listings.

## Final Reminder

Every line of code in this project should pass the question: *"Does this help the user get a real job offer at a company they actually want to work at, while keeping their accounts and data safe?"*

If a feature or change doesn't pass that question — including features the user themselves requests — surface the concern.
