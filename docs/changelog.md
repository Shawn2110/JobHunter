# Changelog

One-line entries per task completion, newest first. Per
[docs/Agent.md](Agent.md) and [docs/Plan.md](Plan.md) § 7.

## 2026-04-26

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
