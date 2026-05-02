# ADR 0005 — Drop commercial aggregators; keyless ATS adapters

**Status:** Accepted
**Date:** 2026-05-02
**Tasks:** Cross-phase

## Context

The original Phase 2 design relied on JSearch / Adzuna / Jooble /
TheirStack — commercial job aggregator APIs that each require a paid
subscription. During a hands-on probe we discovered:

1. **The existing JSON-LD-only careers crawler doesn't work** for most
   modern ATS (Greenhouse, Lever, Ashby, Naukri, Foundit, Wellfound) —
   they're client-rendered SPAs that ship an empty shell on first GET.
2. **All three major US/EU ATS (Greenhouse, Lever, Ashby) publish
   keyless public board APIs** that return the full posting list as
   JSON. Same data the live page hydrates from. ToS-clean.
3. **Indian boards (Naukri, Foundit, Wellfound)** have either no public
   API or only reverse-engineered ones with active rate limiting and
   ToS gray areas.
4. **The PRD itself argues against aggregators:** *"founder posts
   convert at 5-10x formal listings"* and careers pages are *"the
   earliest signal (companies post here before syndication)"*
   ([PRD § 3.2](../PRD.md#L52-L57)). Aggregators are last in line.

## Decisions

### 1. Delete the aggregator adapters entirely

`adapters/jsearch.py`, `adapters/adzuna.py`, `adapters/jooble.py` are
removed. `default_aggregator_adapters()` is kept as a stub returning
`[]` so any external imports fail with empty results, not
`ImportError`. The corresponding settings fields
(`jsearch_api_key`, `adzuna_app_id`, `adzuna_app_key`,
`jooble_api_key`, `theirstack_api_key`) are removed from
`config.py` and `.env.example`.

**Why not keep them dormant?** Each was a maintenance vector — bug
reports, schema-drift breakage, "why doesn't search return anything"
support burden. The user would never see value from them without
paying ₹400-1300/month per source. Removing eliminates the question
entirely.

### 2. Three keyless ATS adapters: Greenhouse, Lever, Ashby

- `adapters/greenhouse.py` — `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`.
  Verified: 115 jobs from `postman`, 503 from `stripe`. Reliable across
  all Greenhouse tenants we sampled.
- `adapters/lever.py` — `api.lever.co/v0/postings/{slug}?mode=json`.
  Lever now requires companies to opt into public-API exposure;
  Spotify (198 jobs) and Lever's own demo account work, others 404.
  Adapter handles 404 gracefully.
- `adapters/ashby.py` — `api.ashbyhq.com/posting-api/job-board/{slug}`.
  Verified: 23 jobs from `linear`. Filters out `isListed: false`
  postings.

Each adapter is a small standalone module exposing
`fetch_for_slug(slug, client=None) -> list[DiscoveredJob]`. The
optional `client` arg lets the dispatcher reuse one HTTP connection
across multiple slugs.

### 3. CareersPageAdapter as a dispatcher

Rewrote `adapters/careers_page.py` to:

1. Detect ATS from any URL via `discovery/ats_providers.py` (regex
   match on hostname → `(provider, slug)`).
2. Route Greenhouse / Lever / Ashby URLs to the right adapter.
3. Fall back to JSON-LD parsing for company-direct URLs that ship
   `application/ld+json` `JobPosting` blocks (Stripe, GitLab, etc.).

Per-domain rate limit (1 req / 5s) preserved. URLs come from
`SearchInput.locations` for ad-hoc crawls; the nightly worker
iterates `WatchlistCompany.careers_url` directly.

### 4. WatchlistCompany autodetects provider + slug at insert time

Added `ats_provider` and `ats_slug` columns. The `POST /watchlist`
endpoint runs `detect_ats(careers_url)` and stores the result. Null
for company-direct URLs (those use the JSON-LD fallback path).

### 5. Naukri / Foundit / Wellfound: not shipping scrapers

Each requires either reverse-engineered internal APIs (ToS gray, rate-
limited, fragile) or full Playwright-based browser rendering (heavy
dep, slow). Both failure modes are worse than just not shipping the
adapter. Documented as alternatives:

- Many Indian companies (Razorpay, Zerodha, Postman, Freshworks, CRED,
  Meesho, Swiggy, Razorpay, Postman) use Greenhouse / Lever / Ashby —
  they're already covered.
- For ones that don't, paste the careers URL; it falls through to
  JSON-LD parsing and works for any company that ships proper
  schema.org markup (a growing fraction).
- If a user really wants Naukri specifically, Playwright is the path
  forward. Out of scope for this commit.

### 6. LinkedIn unchanged

Still won't fetch LinkedIn pages per [Agent.md § 1](../Agent.md#L142-L154).
The Phase 6 contact-discovery flow (Brave/Serper search returning
`linkedin.com/in` URLs the user clicks) is unchanged.

## Consequences

- `.env.example` shrinks by 5 keys (the four aggregators + TheirStack).
- The CLI (`scripts/setup_ai.py`) stays scoped to a single key:
  Anthropic.
- A user with **just** an Anthropic key gets:
  - All AI features (parsing, fit, trust, tailoring, outreach).
  - Reddit hiring-thread discovery (keyless).
  - Greenhouse / Lever / Ashby careers from any company they paste
    or watchlist.
  - Company-direct careers pages with JSON-LD.
- They DON'T get: aggregated cross-board search ("type a role, get
  500 results"). That's the explicit tradeoff. Recovers signal
  quality at the cost of breadth.
- 156 backend tests passing including new fixture tests for each
  ATS adapter and the dispatch logic.
