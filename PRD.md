# JobHunt — Product Requirements Document

**Status:** Draft v1
**Owner:** [Your name]
**Last updated:** 2026-04-26

---

## 1. Vision

JobHunt is an open-source, self-hosted, AI-augmented job-hunting system designed for a single user (you) running their own search. It optimizes for **quality of applications, not quantity** — based on the documented finding that mass-blast tools achieve 0.5-3% response rates while personalization-first approaches achieve 10-15%.

The system handles the four hardest parts of modern job hunting:

1. **Discovery** — finding relevant openings across job boards, founder posts, and careers pages without manual hopping between sites.
2. **Fit assessment** — telling you honestly whether a role is a strong fit, a stretch, or below your level, before you spend time on it.
3. **Resume tailoring** — rewriting your resume per role using AI that mirrors the JD's language without fabrication, and with awareness of how modern ATS actually work.
4. **Outreach drafting** — generating personalized messages to founders/HR/hiring managers that you send manually — never auto-sent.

The system is explicitly **not** an auto-apply tool. The research consensus is unambiguous: auto-apply at scale produces near-zero returns and risks user accounts on platforms like LinkedIn. JobHunt occupies the opposite niche.

## 2. Target User & Scope

**Primary user:** a working professional or fresher running their own job search, comfortable with self-hosting a small app, willing to bring their own API keys for Claude and supporting services. India-first context (Naukri, Foundit, LPA salary norms, DPDP-compliant by design) but globally applicable.

**Scope:** personal use, single-tenant, open source. Not multi-user SaaS. Not a commercial service. This scoping decision materially reduces compliance burden — under India's DPDP Act, purely personal/domestic processing has narrower obligations, and there is no "data fiduciary at scale" obligation.

**Out of scope, explicitly:**
- LinkedIn outreach automation (auto-connect, auto-message) — violates ToS Section 8.2 and risks account bans within hours.
- Auto-apply / form-submission bots — proven low ROI (0.5-3% response rate), accounts get flagged, ATS now actively filters AI-spam.
- LinkedIn profile scraping — violates ToS regardless of "public data" rationalizations.
- Multi-user authentication, billing, team features — single-user only.
- Mobile app (web-first; mobile-responsive but not native).

## 3. Core Capabilities

### 3.1 Persistent Profile

The user sets this up once and updates as life changes. It splits into two layers:

**Verifiable handles** — usernames/URLs the system fetches fresh data from at search time, not at setup time: GitHub, LeetCode, Kaggle, LinkedIn URL, personal portfolio. Why fresh-fetch: a project pushed yesterday matters more than a resume bullet from two years ago.

**Self-reported context** — resume (uploaded once, parsed into structured fields), free-text "about me" narrative, target seniority, work authorization, salary expectations, notice period (India-specific), anti-preferences (industries to avoid, company stages to avoid), past applications log. The "about me" narrative is genuinely valuable — it captures things resumes don't (career transitions, deal-breakers, motivations) and feeds the meta-prompt's positioning strategy.

The resume is parsed once at upload into structured JSON (experience, skills, education, projects). Subsequent searches reference this structured data, not the raw PDF, which saves tokens and produces more reliable AI output.

### 3.2 Search Session

A search is parameterized by: role/title, domain, locations (one or multiple, country/state/city), work mode (remote/hybrid/onsite/any), salary floor, and which discovery modes to use (any combination of the three below).

**Mode 1 — Job aggregators.** JSearch, Adzuna, Jooble, TheirStack APIs return structured listings. Default mode. Latency 1-3s, cheap, broad coverage. India coverage requires mixing multiple providers.

**Mode 2 — Founder/HR posts.** Twitter/X public, Wellfound, Cutshort, Hasjob (India), Reddit job threads, curated newsletters. *Not* LinkedIn — LinkedIn post scraping is ToS-banned. Highest-signal mode (founder posts convert at 5-10x formal listings) but noisy. Latency 5-15s, medium cost.

**Mode 3 — Company careers pages.** User-curated company watchlist. System fetches `/careers` or `/jobs` per company, parses listings, optionally pulls `/about` or `/team` for context. Earliest signal (companies post here before syndication). Background nightly refresh. Latency 10-30s per company on demand, cached otherwise.

Results from selected modes merge into a single feed with source labels (`aggregator` / `founder_post` / `careers_page`). User can filter by source. Deduplication catches the same role across multiple sources.

### 3.3 Stateful Local Index

Every job the system has ever seen is stored locally (SQLite). This unlocks:

- **Diff-based search:** "5 new jobs match your saved search since yesterday."
- **Cross-source dedup:** the same Razorpay listing on LinkedIn + Naukri + careers page becomes one row with three URLs.
- **Semantic search:** embeddings stored per job, so "Python developer" matches a "Backend engineer with Django" listing even without the keyword.
- **Watchlist mode:** marked companies pinged nightly; new postings queued for next morning.
- **Application history:** "you applied to Razorpay 3 weeks ago, no response" — system remembers and surfaces.

### 3.4 Multi-Dimensional Fit Scoring

Each job in the feed gets a fit assessment, *not* a single inflated score. The dimensions:

- **Skills match:** "7 of 10 required skills present. Missing: Kubernetes, gRPC, Kafka."
- **Experience match:** "They want 3-5 years; you have 4. Good fit." or "They want 7+; you have 3. Stretch role."
- **Domain match:** "You've shipped fintech; they're a fintech. Strong signal."
- **Evidence strength:** pulled from GitHub/LeetCode/Kaggle. "Your top GitHub repo (React+TS, 200 stars) maps to their stack."
- **Knockout-question risk:** detected JD requirements likely to appear as binary screening questions (work auth, years of experience, certifications). This is the single biggest cause of auto-rejection and most existing tools ignore it entirely.
- **Honest verdict:** *strong / good / stretch / below-your-level / mismatch.* Including "below your level" matters — it tells the user not to waste effort on roles that under-utilize them. No existing tool gives this verdict because they optimize for engagement, not user outcomes.

### 3.5 AI Resume Tailoring

Architecture: meta-prompting (two-layer).

**Layer 1 — Meta-prompt** analyzes the candidate × role × company × source and produces a structured *tailoring brief* in JSON: positioning strategy, vocabulary shifts, exact-match keywords to add (only those the candidate's experience truthfully supports), what to emphasize, what to downplay, target ATS family if detectable (Workday / Greenhouse / Lever / Naukri / unknown), explicit truthfulness boundaries.

**Layer 2 — Execution prompt** takes the brief plus the resume and produces the rewritten version, constrained by the brief.

The brief is **shown to the user before execution**, editable. This is the differentiator vs. Teal/Jobright — the user sees the AI's strategy and can correct it before any rewriting happens.

The brief encodes correct beliefs about how modern ATS actually work, based on the research:

- Knockout questions cause more auto-rejections than everything else combined; the brief flags them separately for the user.
- Modern ATS (Workday, Greenhouse, Lever) use semantic NLP, but exact matches still score higher; mirror language where truthful.
- Workday-specific: detect `myworkdayjobs.com` URLs, use Skills Cloud canonical names, prefer DOCX upload.
- Single-column layout, standard section headings, parseable formatting are non-negotiable hard constraints, not suggestions.
- Generic AI phrasing is increasingly filtered; the execution prompt forbids common AI-tells.

### 3.6 AI Outreach Drafting

Five-stage flow. See PRD § 4.2 below for the user-facing flow; see Architecture.md § 6 for technical detail.

The user always sends manually. There is no auto-send, no LinkedIn automation, and no integration with the user's email account that bypasses their review.

### 3.7 Application Packaging (not Auto-Submission)

For each job the user wants to apply to, JobHunt prepares the full package: tailored resume (DOCX + PDF), tailored cover letter, draft answers to the 8-10 most common custom questions ("Why this company," "Why are you leaving," etc.), and the contact info if discovered. A companion browser extension autofills application forms when the user clicks "Apply" on the actual ATS page. **The user reviews and clicks submit.** This is the Simplify approach — same outcome as auto-apply, no ToS violations, no account risk.

### 3.8 Contact Discovery (Legitimate Path, No Paid Enrichment)

For each role of interest, the system discovers likely contacts: hiring manager, recruiter (if named), department head, founder/CEO at small companies. The discovery pipeline depends on **no paid third-party data brokers** — all signals come from public, free sources:

- **LinkedIn URL via Google search** (not by scraping LinkedIn). Brave Search or Serper API runs queries like `site:linkedin.com/in "Razorpay" "engineering manager"` and returns top URLs. The user clicks each URL and visits the profile manually. Cheap, ToS-clean.
- **Public signal aggregation** for outreach personalization: company About/Team page, public Twitter/X profile, GitHub if technical, recent news mentions, conference talks, podcasts. None of this requires scraping LinkedIn or paying enrichment APIs.
- **Opportunistic public email** if found during signal aggregation. Many founders and small-company HR contacts publish their email on the company About page, in a Twitter bio, or on a personal site. If the signal aggregator finds one, it's surfaced. There is no fallback to paid email-finder services like Hunter.io or Apollo.

The system delivers: clickable LinkedIn URL, a one-paragraph "what I learned about this person" briefing for the outreach drafter, and a public email if one happens to be findable. The primary outreach channel is **LinkedIn DM, not cold email** — cold email response rates from unknown senders are materially worse, especially in hiring contexts where recruiters check LinkedIn but ignore unknown inbox senders.

Removing the email-finder dependency also eliminates the only external service that processed third-party PII, which simplifies the DPDP compliance picture noticeably.

### 3.9 Trust Assessment (Scam & Ghost-Job Detection)

The 2026 job market has two distinct trust problems and JobHunt detects both:

**Outright scams** — fake postings designed to harvest data, money, or labor. The Indian context is particularly aggressive: in April 2025, UP Police dismantled a Kanpur call center that had defrauded over 1.2 lakh victims using Naukri-sourced resumes; common patterns include pre-offer Aadhaar/PAN requests, "refundable" deposits for laptops or ID cards, fake Naukri "penalty" calls demanding ₹49,000 for ignored emails, WhatsApp/Telegram-only contact, and APK downloads disguised as "company apps." The US FTC reports that job-scam complaints nearly tripled between 2020 and 2024.

**Ghost jobs** — real companies posting roles they have no immediate intent to fill. Independent estimates put the prevalence between 18% and 33% of all online listings; one analysis of US LinkedIn found 27.4% of postings are likely ghosts, with the technology sector showing roughly a 48% non-fill rate. 81% of recruiters in a 2024 survey admitted their employer has posted ghost jobs. Common patterns: listings reposted every 30 days for 6+ months, perpetually-active "evergreen" listings on careers pages, generic "we're always hiring great talent" language with no specific requirements, and listings on LinkedIn that don't appear on the company's actual careers page.

**What JobHunt detects (three layers):**

- **Static rules** (no AI, runs on every job). Detects: upfront-payment language, gmail/yahoo recruiter domains for "big" companies, domain typosquatting (e.g., `infosys-hr.net` for Infosys), WhatsApp/Telegram-only contact mentions, salary outliers (>2.5x median for the role/location), MLM/network-marketing keyword clusters, missing company web footprint, and Indian-specific scam patterns (penalty/fine claims, OTP requests, APK download requests, government-job impersonation outside `.gov.in`/`.nic.in`).
- **AI assessment** (single Claude call per job). Reads the JD + company context + extracted signals and produces a structured verdict with rationale.
- **Longitudinal layer** (runs on watchlist refresh). Flags listings reposted ≥3 times across a 60-day window with minimal description changes — the strongest single ghost-job signal.

**What the system reports.** Each job carries a `trust_verdict` of `verified` / `likely_real` / `suspicious` / `likely_scam` / `unknown`, with structured `scam_signals`, `ghost_job_signals`, `positive_signals`, and a one-paragraph human-readable rationale.

**The verdict is informational, never gatekeeping.** The system never auto-hides "suspicious" jobs — some legitimate roles look unusual (small company, founder-only contact from a Gmail) and the user is the right judge of context. Warnings appear only on the job card when there's something genuinely worth flagging; legitimate jobs show no badge. This mirrors how Gmail handles "suspicious sender" alerts — the user's attention is the scarce resource and is spent only on real signals.

**What the system never does:** auto-block applications, share trust signals with the company, or flag a job purely on the basis of company size or sector. Tech companies have higher ghost-job rates than other sectors — that's information, not a verdict on any specific listing.

## 4. User-Facing Flows

### 4.1 First-Run Setup (one-time)

User installs JobHunt, sets API keys (Claude, Brave Search, JSearch — see Architecture.md for the full list), uploads resume, fills profile (handles + about-me + preferences). System parses resume, validates handles by fetching a small sample (e.g., latest GitHub repo, top LeetCode submission), confirms profile is ready.

### 4.2 Search → Apply Loop (every session)

1. User opens JobHunt, types a search query: role, domain, locations (multi-select), work mode, salary floor.
2. User selects which discovery modes to run (Mode 1 default; Modes 2 and 3 opt-in).
3. System kicks off a batch search. Modes 2 and 3 may take minutes; Mode 1 returns in seconds.
4. Results merge into a feed, sorted by fit score. Each job shows: title, company, location, source label, fit verdict (strong/good/stretch/below/mismatch), trust warning if any (suspicious/likely scam — legitimate jobs show no badge), and a one-line summary.
5. User opens a job. Detail view shows: full JD, fit dimensions breakdown, knockout-question flags, suggested actions ("Tailor resume," "Find contacts," "Draft outreach," "Mark as applied," "Hide").
6. User clicks "Tailor resume." System runs meta-prompt, shows the brief, lets user edit. User clicks "Generate." System produces tailored resume + cover letter + custom-question answers.
7. User clicks "Find contacts." System runs discovery pipeline, returns 3-5 likely contacts with LinkedIn URLs, public emails if found, and personalization briefings.
8. User clicks "Draft outreach" on a contact. System asks the intent (referral / application support / cold introduction), runs outreach meta-prompt, shows brief + draft + reasoning.
9. User edits, copies the message, sends manually via LinkedIn or email.
10. User clicks "Apply" on the actual ATS page. Browser extension autofills standard fields and pre-filled custom answers. User reviews, clicks submit.
11. User marks job as applied in JobHunt. System logs date, attached resume version, attached cover letter, contacted person.
12. Stateful index now reflects the new application; future searches dedupe and recall this history.

### 4.3 Watchlist & Diff Mode (background)

User adds companies of interest to a watchlist. Nightly background job fetches each company's `/careers` page, diffs against the local index, queues new listings to the morning feed with a "new since yesterday" label.

## 5. Anti-Patterns — What Not to Build

These aren't "nice-to-have to avoid"; they're hard constraints based on the research:

- **No LinkedIn automation of any kind.** No auto-connect. No auto-message. No scraping profiles or posts. The user's primary professional account is more valuable than any feature this would enable.
- **No auto-submit of applications.** Browser extension autofills, user reviews, user clicks submit.
- **No fabrication in resume tailoring.** The execution prompt must be hard-constrained against inventing experience. Rephrasing existing experience is allowed; claiming experience that doesn't exist is not.
- **No "ATS score" theater.** The research is clear that "ATS scores" are mostly marketing. The system reports concrete dimensions (skills present/missing, knockout risk, semantic match strength) instead of an inflated single number.
- **No single-number fit scores.** Always multi-dimensional, always with an honest verdict including "below your level."
- **No mass-blast workflows.** The product is built around 5-30 high-quality applications per week, not 500 low-quality ones.
- **No engagement-optimization patterns.** No artificial gamification, streak-tracking, or "you've applied to 500 jobs!" pressure. The user's success metric is offers, not application count.
- **No data exfiltration.** All user data stays local. API keys are user-supplied. No telemetry, no usage tracking, no server-side logging.
- **No silent AI overrides.** When the AI rewrites something, the user sees the brief and the reasoning. No black boxes.

## 6. Product Behavior Principles

These shape the user experience across every feature:

**Honesty over flattery.** The system tells the user when a role is a stretch, when their resume isn't strong enough, when an outreach message has no real personalization signal to anchor on. This is the inverse of how engagement-optimized products behave and is the entire point of building your own tool.

**The user is the captain.** The AI proposes; the user disposes. Every AI output is accompanied by the brief that produced it, editable. Nothing happens without user review.

**Local-first, BYO-keys.** Everything runs on the user's machine. The user provides their own API keys. The user's data is theirs.

**Quality bar over feature count.** Each feature should work well or not exist. A half-working contact-discovery feature is worse than no feature.

**Privacy by default.** Decline cookies, refuse trackers, never log personal data. India's DPDP Act compliance is the floor, not the ceiling.

**Skills-Cloud-aware, not keyword-stuffer.** Modern ATS use semantic matching. The meta-prompt understands this. The system never produces resume language that's "optimized" at the cost of readability — that approach is increasingly being filtered as AI-spam.

## 7. Success Metrics

Personal-use metrics, tracked locally only:

- **Application-to-response rate** by source mode (aggregator / founder post / careers page) — this tells you which discovery channels are working for you.
- **Time per application** — should trend down as the system removes friction.
- **Fit-verdict accuracy** — when "strong" verdicts get rejected and "stretch" verdicts get callbacks, the meta-prompt's fit logic needs adjustment.
- **Cost per application** — should stay around ₹15-40 all-in (Claude + search APIs + enrichment).

Notably **not** a metric: applications submitted per week. Volume is anti-goal.

## 8. Cross-References

- Technical architecture: see **Architecture.md**
- Build sequence and milestones: see **Plan.md**
- Coding rules and AI agent constraints: see **Agent.md**
- UI/UX direction: see **Design.md**
