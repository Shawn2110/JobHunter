# ADR 0001 — Initial repository scaffold

**Status:** Accepted
**Date:** 2026-04-26
**Task:** P0-T1

## Context

JobHunt is starting from five planning docs and zero code. P0-T1 lays
down the directory tree, dependency-free config files, and the
prompt-loader specification, before any backend or frontend code is
written in P0-T2 / P0-T3.

## Decisions

### 1. Provider keys are user-pick-your-own, not required at startup

Every external service in `.env.example` is grouped by category (AI,
job aggregators, search, crawler, signals). Only `ANTHROPIC_API_KEY`
will be required once AI features are enabled (Phase 1+). For each
other category the user picks at least one provider; the backend
detects which keys are present at startup and only enables those
providers.

**Why:** the user explicitly asked to pick which providers to use, and
the architecture already supports this through provider-agnostic
adapters ([docs/Architecture.md § 5.1](Architecture.md)).
Hard-requiring every key at boot would force the user to pay for
services they don't need.

### 2. No Dockerfiles in P0-T1

`docker-compose.yml` is committed but the per-service Dockerfiles land
with the apps in P0-T2 (backend) and P0-T3 (frontend). YAML is valid;
`docker compose config` will succeed. `docker compose up` will only
work after both Dockerfiles are in place.

**Why:** keeps each task's scope tight. The Dockerfile depends on the
app's dependency manifest, which doesn't exist until the next task.

### 3. Single root `.gitignore` covering Python, Node, secrets, data

Rather than three separate `.gitignore`s. The `frontend/` folder may
get a small additional one when `next dev` regenerates `next-env.d.ts`,
but for now one file is simpler.

### 4. `extension/`, `scripts/`, `data/` use `.gitkeep` placeholders

Per [docs/Agent.md](Agent.md), no documentation files unless required.
A bare `.gitkeep` is enough to commit an otherwise-empty directory; the
purpose of each folder is documented in [docs/Architecture.md](Architecture.md)
and [docs/Plan.md](Plan.md).

### 5. Prompt loader spec lives at `prompts/__loader__.md`

Documents the frontmatter contract every prompt file must follow. The
implementation (`backend/app/ai/prompt_loader.py`) lands in P0-T4. The
spec is committed first because it's the contract that subsequent
prompt files must respect.

### 6. Micro-commit policy

Per user instruction, every file change is committed individually
("each file = one commit"). This applies to all scaffolding work going
forward. The pre-existing rename of planning docs into `docs/` was
treated as one atomic move (single commit), since git's rename detection
collapses it that way.

## Consequences

- Setup story for the user: `cp .env.example .env`, fill in only the
  keys they want, `docker compose up`. Clean and documented.
- The first time someone runs `docker compose up` after a fresh clone,
  it will fail until P0-T2 and P0-T3 land. README acknowledges this.
- Many small commits in the early history. Acceptable trade-off given
  the user's explicit preference and the early-stage nature of the
  project.
