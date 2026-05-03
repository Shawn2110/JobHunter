# ADR 0006 — v1 / v2 product split

**Status:** Accepted
**Date:** 2026-05-04
**Tasks:** Roadmap-shaping

## Context

Through the LinkedIn / Apify / scraping conversations we converged on
two distinct product surfaces, both legitimate but for different
moments in the user's workflow:

1. A **web application** at `localhost:3000` where the user manages
   their profile, runs JobHunt-native discovery, and reviews / tailors
   saved jobs.
2. A **browser extension** that lives wherever the user actually
   browses for jobs (LinkedIn, Naukri, Indeed, etc.) and overlays
   JobHunt's intelligence on the page they're already looking at.

These overlap on the backend (same models, same prompts, same trust /
fit / tailoring pipelines) but the frontends are architecturally
distinct enough to warrant explicit version planning. Trying to
build both surfaces simultaneously risks half-finishing each.

## Decision

Ship as **v1** (web app + thin extension) and **v2** (extension as
primary surface). Same backend, same models, same prompts. Frontends
evolve in two distinct waves.

### v1 — Web app product, extension as save-and-redirect helper

**Mental model:** the user lives at `localhost:3000`. The web app is
where they configure, search, view, save, tailor, and apply. The
extension exists but does only one thing: on a job page, save URL +
title (and ideally JD text via per-portal selectors) → web app
ingests + processes → user opens JobHunt to review the package.

**Frontend surface (shipped):**
- `/` — backend status + provider checklist
- `/profile` — full profile editor + resume upload
- `/search` — JobHunt-native search (Greenhouse / Lever / Ashby +
  Reddit). Plus a "Search elsewhere" panel of deep-link buttons to
  LinkedIn / Naukri / Indeed / Foundit / Wellfound / Glassdoor —
  user clicks to open the portal's native search in a new tab.
  *(Deep-link panel: planned, not yet shipped.)*
- `/jobs/[id]` — job detail with fit + trust + knockouts
- `/jobs/[id]/package` — generate / view / regenerate the tailored
  resume, cover letter, and custom-question answers; deep-link to
  ATS application

**Backend surface (shipped):**
- All discovery adapters, all AI services, all trust / fit pipelines.
- Tailoring + cover-letter + custom-questions endpoints.
- Watchlist + nightly worker.

**Extension surface (v1 minimum):**
- Existing autofill bar on supported ATS pages
- Existing popup "Save to JobHunt" button (URL + title only)
- *(v1.x: enhance save to include DOM-extracted JD text per portal,
  one portal at a time starting with Naukri)*

**Optional v1 add-on (Apify for non-LinkedIn SPAs):**
A single discovery adapter that hits Apify's REST API to fetch jobs
from Naukri / Foundit / Wellfound (SPA sites that broke our keyless
crawler). Triggered by user pasting one of those URLs into the
watchlist. Costs ~₹0.50-2 per Actor run. Excludes LinkedIn entirely
— the legal exposure profile is materially different. Not shipping
in this commit; tagged v1.x.

### v2 — Extension as primary surface

**Mental model:** the user lives in their browser, on whichever
portal they prefer. Open a job posting; the extension overlays a
JobHunt panel on the page itself with live fit + trust + knockouts.
Save & tailor happens in-place; the web app is just a backend you
rarely visit (for setup, watchlist, applications history).

**Surface (proposed, not yet shipped):**

- New backend endpoint `POST /extension/score` — accepts JD payload
  from extension, runs fit + trust + knockouts, returns scores
  without persisting anything (live preview).
- New backend endpoint `POST /extension/save-and-package` — accepts
  same payload + resume_id, persists Job, runs tailoring + cover
  letter + custom answers in background, returns a package_id.
- Per-portal JD extractors in `extension/content.js` (~50 lines per
  portal): LinkedIn, Naukri, Indeed, Greenhouse, Lever, Ashby, etc.
- In-page overlay UI rendered on supported job pages:

  ```
  ┌─────────────────────────────┐
  │  JobHunt assessment          │
  │  Fit: Strong (8/10 skills)   │
  │  Trust: ✓ No flags           │
  │  Knockouts: 1 (work auth)    │
  │  ───────                     │
  │  [Save & tailor]             │
  └─────────────────────────────┘
  ```

- Toast progress notifications during background tailoring
- Web app's `/search` and `/jobs` pages stay; primary entry shifts
  to extension

## What's NOT being built either way (still)

- **No JobHunt-side LinkedIn fetching.** Reading a LinkedIn page in
  the user's logged-in browser via the extension is fine
  (DOM-extraction in user's session ≠ server-side scraping). Server-
  side fetching of linkedin.com remains forbidden — guarded by
  [`tests/discovery/test_no_linkedin.py`](../../backend/tests/discovery/test_no_linkedin.py).
- **No mass scraper webapp.** Initially proposed as part of the
  split; rejected because v2's extension provides discovery via the
  user's natural browsing, making a parallel scraper redundant. The
  Apify add-on for Naukri/Foundit/Wellfound is a small, on-demand
  fallback, not a mass scraper.
- **No Twitter / Wellfound API integration.** Both gated by paid
  APIs we're not building toward.

## Why this split is the right shape

**v1 ships immediately and is fully usable.** Discovery via
keyless ATS adapters + Reddit + watchlist URLs. Save via extension
popup. Tailor via web app. The user can run a real job hunt with
just v1.

**v2 makes the workflow native to where the user already is.** No
context switch from LinkedIn to JobHunt to read a fit score. Same
backend, richer frontend.

**Both surfaces share 100% of the backend.** No dual-stack burden;
adding a feature to one is trivial to expose in the other.

**Apify question is settled.** Outsourcing scraping to Apify is not
materially different ToS-wise from doing it ourselves — the data
acquisition is what matters, not who runs the scraper. Apify is
**only** considered as a v1.x add-on for Naukri / Foundit / Wellfound
(SPAs we can't render with plain `httpx`), explicitly excluding
LinkedIn.

## Build order

```
v1 wave 1 (backend foundations) — DONE
├── Discovery: keyless ATS + Reddit
├── Profile / resume / fit / trust / knockouts
├── Watchlist + nightly worker
├── Resume tailoring backend (P4-T1..T3, T5 backend)
└── Truthfulness post-check + Critical Do-Not-Break tests

v1 wave 2 (frontend completes the loop) — IN THIS COMMIT
├── Cover-letter service + endpoint
├── Custom-questions endpoint
├── /jobs/[id]/package page (generate / view / copy / regenerate)
└── Wire job-detail "Tailor" button to package page

v1.x (planned next)
├── Search-elsewhere deep-link panel on /search
├── Extension content.js JD extractor for ONE portal first (Naukri)
├── Extension's save endpoint accepts the rich payload (JD text +
│   company + location)
└── Apify adapter for Naukri/Foundit/Wellfound SPA fallback (opt-in)

v2 wave 1
├── /extension/score endpoint
├── In-page overlay UI in content.js
├── Per-portal JD extractors (rest)
└── Save-and-package endpoint with background processing

v2 wave 2
├── Toast progress notifications
├── Per-portal autofill selectors
└── Frontend deprioritization (web app shrinks to setup + history)
```

## Consequences

- A fresh user can set up profile + upload resume + open the
  package page and get a real tailored resume / cover letter / custom
  answers for any job they save through the extension popup or paste
  into the watchlist. End-to-end works as of this commit.
- The "Tailor resume" button on the job-detail page now actually
  works (used to be a disabled placeholder).
- Plan.md's older Phase 4 / Phase 5 / Phase 7 markers are subsumed
  into v1; the v2 work isn't in any prior phase numbering — it's
  net-new product surface.
- ADR 0004's deferred list is partially resolved: cover letter +
  custom questions + tailoring UI are all shipped now. DOCX render
  and frontend pages for contacts / outreach / watchlist /
  applications remain deferred to v2 or beyond.
