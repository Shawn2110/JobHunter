# Changelog

One-line entries per task completion, newest first. Per
[docs/Agent.md](Agent.md) and [docs/Plan.md](Plan.md) § 7.

## 2026-04-26

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
