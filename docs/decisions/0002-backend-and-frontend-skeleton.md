# ADR 0002 — Backend and frontend skeleton choices

**Status:** Accepted
**Date:** 2026-04-26
**Tasks:** P0-T2, P0-T3

## Context

P0-T2 stands up a FastAPI backend with SQLAlchemy + Alembic + Pydantic
Settings. P0-T3 stands up a Next.js 15 frontend that calls `/health`.
The choices below were either non-obvious or easy to revisit later if
they turn out wrong.

## Decisions

### 1. Pydantic Settings — every provider key is `Optional[str] = None`

The backend boots with no `.env` configured. At startup, structlog
logs which providers are detected and warns when AI / aggregators are
missing — but never raises. This keeps the early-phase developer loop
fast (`docker compose up` works on a fresh clone) and reflects the
user-facing contract that providers are pick-your-own.

`ANTHROPIC_API_KEY` will become a hard requirement once Phase 1 wires
in AI features; until then a warning is the right surface.

### 2. `/providers` endpoint reports configured booleans, never the keys

The frontend needs to know which categories are configured to render
the checklist. Returning the keys themselves would violate
[docs/Agent.md § API Key Handling](../Agent.md). The endpoint returns
booleans / lists / canonical names only.

### 3. Single `Settings()` instance imported from `app.config.settings`

Pydantic Settings is instantiated once at import time. Every other
module reads `settings.field`. No `Depends(get_settings)` boilerplate;
no global mutable state. If a test ever needs to override settings,
`monkeypatch.setattr` on the singleton is the escape hatch.

### 4. Async SQLAlchemy 2 with `aiosqlite`

Architecture.md specifies async I/O end-to-end. `aiosqlite` is the
async driver SQLite needs to play with SQLAlchemy's `AsyncSession`.
Synchronous SQLAlchemy would force `run_in_executor` calls in every
DB-touching service — needless complexity given async is the FastAPI
default.

### 5. Alembic from day one, even with zero migrations

`migrations/versions/` is empty in P0-T2 but the framework is wired
up. Adding Alembic later means writing the bootstrap migration by
hand. The cost of adding it now is a single `alembic.ini` and a 60-line
`env.py`. The first real migration lands with P1-T1 (profile model).

### 6. Next.js App Router, not Pages Router

The Architecture document picked App Router. Confirming the choice:
the AI panels in PRD § 3.5 / § 3.6 will benefit from server actions,
suspense streaming, and `loading.tsx` patterns that are App-Router
native.

### 7. shadcn/ui copy-not-install pattern, manually

Rather than `npx shadcn-ui init` (which would generate a bunch of
files we don't need yet), we hand-wrote the minimum: `components.json`,
`lib/utils.ts` with `cn()`, and `components/ui/badge.tsx`. Future
primitives (Button, Card, Dialog, Input, Select) get added one at a
time when an actual screen needs them. Avoids a 20-file shadcn dump
that mostly sits unused for weeks.

### 8. No TanStack Query in P0-T3

Architecture.md specifies TanStack Query for server state. P0-T3 has
exactly two endpoints to call once on page load — adding a
`QueryClientProvider` and wrappers would be theatre. TanStack Query
goes in with P1-T3 (Profile UI), where there's actual server state to
manage (mutations, cache invalidation, dependent queries).

### 9. `outputFileTracingRoot` pinned in `next.config.mjs`

Next.js was inferring a parent directory as the workspace root
because of unrelated `package.json` files higher up the host's path
(`C:\Users\Asus\package-lock.json`). Pinning the trace root prevents
incorrect bundling in Docker builds and silences the build warning.

### 10. Python 3.14 works; pyproject still targets `>=3.12`

The dev machine has Python 3.14. All current deps install and tests
pass on it. Keeping `requires-python = ">=3.12"` in `pyproject.toml`
matches the floor stated in [docs/Agent.md](../Agent.md) and gives
users a wider compatible range. We re-evaluate if a dep breaks on a
specific minor version.

### 11. Web app uses warm off-white background per Design.md

`#FAFAF9` body background, set in `globals.css`. Full design-system
work (typography, spacing scale, semantic verdict colors) is deferred
to the phases that introduce the screens those tokens belong to —
trying to design the entire visual system in P0-T3 would be premature.

## Consequences

- A fresh clone runs `cd backend && pip install -e ".[dev]" && pytest`
  and gets two passing tests in about a second.
- A fresh clone runs `cd frontend && npm install && npm run build` and
  gets a clean production build.
- `docker compose up` requires the user's `.env` to exist (even if
  empty) because compose treats missing env_file as a hard error. The
  README will document `cp .env.example .env` as the first step.
- No real DB is created until Phase 1 introduces the first migration.
  The `data/` directory exists and is gitignored.
