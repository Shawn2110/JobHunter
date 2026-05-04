# ADR 0007 — v2 wave 1: extension is the primary product surface

**Status:** Accepted
**Date:** 2026-05-04
**Tasks:** v2 wave 1 (extension overlay + backend score endpoints +
            frontend re-framing)
**Supersedes (in spirit):** ADR 0006's v2 plan, now executed

## Context

ADR 0006 split the product into v1 (web app + thin extension) and
v2 (extension as primary surface). The user confirmed v2 is the
intended end state — the extension should be where they live, not
the web app.

This ADR records the v2 wave 1 implementation: the smallest end-to-
end path that delivers the extension-first experience.

## Decision

### Backend: two new endpoints, both stateless or commit-only

**`POST /extension/score`** — live preview path. Accepts the JD
payload the content script extracts, runs:
1. `extract_knockouts` (always)
2. `compute_trust_dict` (always — Layers A + B; skips Layer C
   longitudinal since there's no Job row to attach a sighting to)
3. `compute_fit_dict` (only when profile + master resume exist;
   `notes` array surfaces the gaps otherwise)

Returns a combined dict matching the same shapes the persisted
FitAssessment / TrustAssessment use, so the same UI logic can render
either preview or persisted verdicts. **Critical:** persists
nothing. The 95% of jobs the user looks at and skips leave no trace
in the DB. Guarded by `test_score_does_not_persist_anything`.

**`POST /extension/save-and-tailor`** — commit path. Persists
Job + JobSource (deduped on `apply_url`), returns a `package_url`
the overlay deep-links to. Doesn't run tailoring inline (30-60 sec
is too long for an overlay loading state); the package page
generates on first open. Surfaces `tailoring_status`
(`kicked_off` / `skipped_no_profile` / `skipped_no_resume`) so the
overlay can warn the user about gaps before they click through.

To enable both endpoints without duplicating prompt-rendering logic:

- `compute_fit_dict` extracted from `assess_fit` in `app/ai/fit.py`
- `compute_trust_dict` extracted from `assess_trust` in
  `app/trust/service.py`

The persisting wrappers (`assess_fit` / `assess_trust`) now call
the stateless versions internally.

### Extension: in-page scoring overlay

`extension/content.js` mounts a small floating panel (top-right,
340px wide) on supported job pages whenever the existing
`extractJobFromPage()` returns a description longer than 200 chars
(heuristic that filters out search-result and landing pages).

**Initial state is opt-in.** The overlay first shows a small
'Score this job?' card with a one-button trigger. We don't
auto-trigger scoring on every page load because that costs
Anthropic tokens per visit and the user may have opened 12 tabs to
browse. Click → POST `/extension/score` → expand to full panel.

**Full panel sections:**
- Fit: color-coded verdict badge per [Design.md § 5.2] + summary
  line + skills score
- Trust: badge per [Design.md § 4.3] (only when concerning;
  '✓ no flags' otherwise) + top 3 scam signals + top 2 ghost
  signals
- Knockouts: top 4 detected knockout questions
- Actions: 'Save & tailor' (POST `/save-and-tailor` → deep-link
  to package), 'Just save' (POST `/save-job` — no AI), Close

**SPA navigation handled.** LinkedIn / Naukri / Wellfound change
URL without a full page load; setInterval watches `location.href`
and re-mounts on URL change with a 1.5s delay for re-paint.

**Coexists with the existing autofill bar** — both can show, but
they target different page contexts (autofill is for application
forms, scoring overlay is for JD pages). DOM positions don't
conflict (overlay top-right, autofill bottom-right).

### Frontend: re-framed for setup + review

The web app didn't go away — it's still where:
- Profile is set up (one-time; couldn't fit in extension popup)
- Tailored packages are reviewed at `/jobs/[id]/package`
- Optional JobHunt-native discovery happens at `/search`

But the entry-point messaging shifted:

- `Nav.tsx`: small teal pill next to the logo —
  'extension is the main surface'
- `app/page.tsx`: prominent 'Use the extension' card with
  load-unpacked install steps; secondary 'This web app is for'
  card listing the remaining web roles. Replaces the old
  'Set up profile and run a search to begin' framing.

## What v2 wave 1 explicitly does NOT include

These are deferred to v2.x or later — design is intentional, not
oversights:

- **Background tailoring** when 'Save & tailor' is clicked. Today
  we persist the Job and the package page generates on first open
  (the user clicks through to the web app). v2.x can add a
  background worker that pre-generates so the package is already
  built when the user lands on it.
- **In-overlay tailoring review** (showing the rewritten resume
  inside the extension). Decided against because the overlay has
  limited real estate and copying long-form Markdown out of an
  overlay is awkward. The web app's package page handles this
  better.
- **Per-portal selector tuning.** Current SELECTORS dict has
  educated guesses for Naukri / Greenhouse / Lever / Ashby /
  Foundit / Wellfound / Workday + generic h1/title/main fallbacks.
  Real-page testing will reveal selectors that need adjustment;
  patches go in the same file with no schema changes.
- **Cost ticker in the overlay** showing how much Anthropic spend
  this session is using. Useful but not critical for first cut.
- **Watchlist + nightly worker integration with the overlay** —
  e.g., 'this company is on your watchlist, X new jobs this week'.
  Phase-9-related; later.
- **Outreach / contact discovery in-overlay.** Phase 6 + Phase 7
  backend exists but no UI in either web app or extension. Lower
  priority than the score-and-save flow.

## What stays unchanged from v1

- All backend AI services (fit, trust, tailoring, cover letter,
  custom Q's). v2 layers a richer client on top of the same
  backend.
- All Critical Do-Not-Break tests:
  - `test_no_autosubmit` — extension never calls .submit / etc.
  - `test_extension_uses_only_localhost_backend`
  - `test_no_linkedin` (backend never fetches LinkedIn)
  - `test_no_external_trust_share`
  - `test_truthfulness_check`
  - `test_no_auto_hide` (trust never gates jobs)
  All still pass.
- Web app routes: `/`, `/profile`, `/search`, `/jobs/[id]`,
  `/jobs/[id]/package` — unchanged. They've been re-framed in
  copy but not removed.
- Search-elsewhere panel from v1.x — still on `/search`. Useful
  even with extension since you can launch a search across
  portals from one place.

## Consequences

- A user with the extension loaded + Anthropic key set + profile
  set up + master resume uploaded gets the full v2 experience:
  open any supported job page → click 'Score this job' → see fit,
  trust, knockouts → click 'Save & tailor' → land on the package
  page with everything generated.
- A user without the extension can still use JobHunt entirely
  through the web app — `/search`, watchlist, save, view package.
  v2 doesn't break v1; it adds a primary path that didn't exist.
- The `/jobs/[id]/package` page becomes much more important —
  it's the place where extension-saved jobs become useful. Future
  work to pre-generate tailoring artifacts (so the page loads
  ready, not "click to generate") is the natural next step.
- Overlay tuning (selectors, layout, copy) will need iteration
  based on real-page testing. Build is intentionally minimal-
  viable; we'd rather ship and tune than ship polished-but-wrong.
