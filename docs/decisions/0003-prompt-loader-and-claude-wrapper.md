# ADR 0003 — Prompt loader and Claude wrapper

**Status:** Accepted
**Date:** 2026-04-26
**Tasks:** P0-T4, P0-T5

## Context

P0-T4 lands the prompt loading framework that every meta-prompt and
execution-prompt in Phase 4+ will use. P0-T5 lands the Claude wrapper
that consumes loader output and persists per-call cost rows. These
two tasks shape the AI surface area for the rest of the project.

## Decisions

### 1. Frontmatter contract is YAML, body is plain Markdown

`prompts/__loader__.md` already documented the contract; P0-T4
implements it. The frontmatter is parsed with `pyyaml.safe_load` and
validated against the `PromptManifest` Pydantic model. Strict
validation at load time is preferred over lenient parsing — a typo in
a prompt manifest should surface as a clear error before the AI is
invoked, not as a silent default.

### 2. Template substitution is regex, not Jinja2

The loader supports a strict subset of Jinja2: just `{{ var_name }}`
variable replacement. No conditionals, no loops, no filters. Regex
implementation (`_PLACEHOLDER_RE`) is ~5 lines and has zero deps
beyond the stdlib.

We promote to real Jinja2 only when a prompt genuinely needs
conditional or loop logic. So far, every meta-prompt described in
Architecture.md § 5.2 takes structured inputs and embeds them as JSON
or plain strings — no control flow needed.

### 3. Loader hot-reloads on every call (no caching)

Per `prompts/__loader__.md`. The file system read on each call is
~1ms; the productivity win from "edit prompt → next request reflects
the change" is worth that. If we ever measure a real overhead in a
high-frequency call site, we add a versioned cache then.

### 4. Filename, directory, and frontmatter must agree

`load("static", "echo")` checks that the file is at
`prompts/static/echo.md`, its frontmatter says `name: echo`, and its
frontmatter says `kind: static`. Disagreement raises immediately. This
catches the most common mistake (rename file but forget to update the
manifest's name) before it leads to confusing call-site errors.

### 5. `output_schema: "string"` is a special-cased literal

For prompts where the model returns free-form prose (a draft outreach
message, a cover letter), `output_schema: string` is enforced as
`isinstance(response, str)`. Everything else is treated as a JSON
Schema and run through `Draft202012Validator`. This keeps the schema
field uniform across all prompt files without forcing prose prompts
to declare a trivial `{"type": "string"}` schema.

### 6. ClaudeClient accepts `str | RenderedPrompt` polymorphically

A single `complete()` method handles both raw strings and
manifest-driven `RenderedPrompt` inputs. With `RenderedPrompt`, the
manifest's model / max_tokens / temperature win unless the caller
explicitly overrides. With a raw string, the client's `default_model`
and conservative defaults (4096 tokens, 0.2 temperature) apply.

This avoids duplicating the call path and keeps service code clean
(`await claude.complete(rendered)` is the dominant call shape).

### 7. AI cost estimation uses an editable price table, not API metadata

Anthropic's API doesn't return cost in the response — the SDK gives us
input_tokens and output_tokens, and we multiply by a local price
table (`PRICES_USD_PER_M_TOKENS`). The user can edit the table when
prices change. Unknown models return `cost_usd = None` rather than
raising — logging never blocks on a missing price entry.

Future work: `python anthropic-cost` or similar packages could keep
the table fresh. Not worth the dep yet.

### 8. `ai_call` row is best-effort (session is optional)

`ClaudeClient.complete()` accepts `session: AsyncSession | None`. When
provided, every call writes a row with `kind / name / version / tokens
/ cost / duration / succeeded / error_message`. When `None`, the call
still completes — just without the DB write. This keeps the wrapper
testable without a database fixture and lets internal scripts or
one-off tools call the wrapper without first wiring up sessions.

### 9. `ai_call` table never stores prompt or response bodies

Only metadata — `prompt_kind`, `prompt_name`, `prompt_version`, token
counts, cost, duration. The user's actual prompts and AI outputs live
in `tailoring_brief`, `tailored_artifact`, `outreach_draft`, etc. (all
landing in later phases). Keeping `ai_call` metadata-only means the
table stays small (kilobytes per month at v1 volumes) and doesn't
accidentally hold a copy of the user's resume or sensitive content.

### 10. `frozen_claude` fixture replaces SDK, not HTTP layer

The `frozen_claude` fixture in `conftest.py` swaps
`AsyncAnthropic.messages` with a `_FakeMessages` recorder that
returns a fixed response. We do **not** stub at the HTTP level
(`pytest-httpx`) because it would couple tests to the SDK's wire
format, which Anthropic can change between SDK versions.

The fake records every call so tests can assert on the args (model,
max_tokens, temperature, message content). Per Agent.md § Testing:
"Tests for AI-using services should use frozen fixture responses…
Never hit the live Claude API in CI."

### 11. First Alembic migration includes only `ai_call`

The first revision creates `ai_call` plus its two indexes
(`created_at` for time-window queries; `prompt_name` for per-prompt
cost rollups). Profile / job / tailoring / contact / outreach tables
land in their respective phase tasks (P1-T1, P2-T1, etc.) as separate
migrations. Keeps each migration small and reviewable.

### 12. Default `DATABASE_URL` resolves to repo-root absolutely

Discovered while running `alembic revision --autogenerate`: the
previous default `./data/jobhunt.db` resolved relative to wherever
the process was launched from, which broke when alembic ran from
`backend/`. Fixed in this turn — the default now resolves to
`<repo_root>/data/jobhunt.db` using `Path.as_posix()` so the URL is
well-formed on Windows. Users can still override via `.env`.

## Consequences

- Every meta-prompt and execution-prompt added in Phase 4+ uses the
  same loading + validation surface, with the manifest as the single
  source of truth for model, token budget, and output shape.
- Adding a new prompt is one file, no code changes. Editing one is
  the same — no restart.
- The cost dashboard (P10-T2) reads directly from `ai_call`. No
  separate logging pipeline required.
- AI-using service tests follow the `frozen_claude` pattern from day
  one. The "do not hit the real API in CI" rule has a working escape
  hatch.
- Phase 0 is closed. The system can boot, render a status page, parse
  prompts, and call Claude. Nothing more, nothing less.
