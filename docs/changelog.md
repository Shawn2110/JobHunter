# Changelog

One-line entries per task completion, newest first. Per
[docs/Agent.md](Agent.md) and [docs/Plan.md](Plan.md) § 7.

## 2026-04-26

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
