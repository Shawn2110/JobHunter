# JobHunt — Design Document

**Status:** Draft v1
**Last updated:** 2026-04-26

This document describes the visual and interaction design direction for JobHunt, drawing from competitive analysis of Teal, Huntr, Jobright, Simplify, Notion, Linear, and a few editorial/calm-productivity references. It defines what we copy, what we improve, and what we deliberately reject.

For the *what* we're building, see PRD.md. For the *how*, see Architecture.md.

---

## 1. Design Philosophy

JobHunt exists to help a user make *fewer, better* job applications. The visual and interaction design must reinforce that disposition at every turn.

The dominant aesthetic across competitive job-hunting tools is what could be called **dashboard maximalism**: pipeline view with kanban columns, application counters, "you're on a 7-day streak" badges, conversion funnels, achievement celebrations. This UX language is borrowed from sales CRMs, where activity-volume genuinely correlates with outcomes. For job hunting, it doesn't — it inverts the user's incentives.

JobHunt rejects that pattern. The aesthetic instead is **focused calm**: closer to Linear or Notion than to Salesforce or HubSpot. The interface should feel like a research notebook a thoughtful person uses, not a sales dashboard.

Three concrete guiding principles fall out of this:

**Surface signal, not activity.** The home screen shows what's *new and worth your attention*, not how many applications you've sent. There is no application counter. There is no streak. There is no "level up your search" gamification.

**Show the AI's reasoning.** Every AI output is presented alongside the brief that produced it. This is the entire differentiation vs. Teal/Jobright/Huntr — they hide the reasoning, we expose it.

**One-screen workflows.** Resume tailoring, contact discovery, outreach drafting — each is a single page with everything needed in view. No multi-step wizards, no modal-on-modal. The user can see the input, the AI's strategy, and the output simultaneously.

## 2. Competitive References — What to Borrow, What to Reject

### Teal HQ

**Borrow:**
- Clean job card grid as the primary surface
- "Match score" pulled from the JD with keyword highlighting
- Three-pane layout for resume editing (original / brief / output) — Teal does this for resume vs JD comparison

**Reject:**
- The single-number "match score" inflated to feel good. Replace with multi-dimensional fit.
- Generic "Career Hub" content modules that pad out the dashboard.
- Resume templates that look polished but hide ATS-incompatible formatting.
- The pricing-pressure UX (locked features behind a glowing "upgrade" button).

### Huntr

**Borrow:**
- Kanban-style application tracker as a *secondary* view (not primary).
- The browser extension's one-click job-save flow.

**Reject:**
- Kanban as the home screen. Kanban over-emphasizes pipeline volume and makes a quiet, slow week feel like failure.
- Heavyweight CRM patterns (custom fields, contact pipelines, deal stages). Most of these are sales-CRM drift.

### Jobright

**Borrow:**
- "Insider Connections" concept — surfacing real people at the target company, not just listings.
- Daily digest of new matches.

**Reject:**
- US-only mental model.
- "AI Agent" auto-apply messaging — JobHunt is explicitly the opposite.
- The credit-counter UI that creates anxiety about running out of free uses.

### Simplify Jobs

**Borrow:**
- The browser extension UX is exemplary: minimal popup, clear field-by-field autofill, never auto-submits. JobHunt's extension follows this pattern.

**Reject:**
- "Apply to 100 jobs" framing on their landing page (which the actual product doesn't really deliver).

### Notion / Linear / Cron / Things 3

**Borrow:**
- Editorial calm. Generous white space. Few colors used with intention.
- Keyboard-first navigation. `cmd-K` everywhere.
- Subtle, content-focused typography.
- Inline editing where it makes sense; modals where they don't.
- Linear's "what's new since you last checked" pattern for the diff feed.

These products know that a tool used daily for hours should feel quiet, not energetic. JobHunt should feel the same.

## 3. Information Architecture

The app has **five top-level routes**, accessible from a persistent sidebar:

```
[Logo]                    
                          
  Today          ⌘1       Default landing — diff feed: what's new since last visit
  Search         ⌘2       Run a new search; saved searches; recent results
  Jobs           ⌘3       The full job index; filtered views
  Applications   ⌘4       What you've applied to; status tracking
  Watchlist      ⌘5       Companies you're watching; their latest postings
                          
  [Profile, settings — bottom of sidebar]
```

The sidebar is collapsible. Default width 240px, collapsed 60px (icons only).

**No sub-navigation tabs within pages where avoidable.** If a page needs sub-navigation, it lives as inline filter chips at the top of the content area, not as a second nav layer.

## 4. Key Screens

### 4.1 Today (default landing)

A single column, 720px max width, centered. Three sections, in order:

**"New since you last looked"** — diff feed. Cards for jobs first seen since the user's last session. Each card shows: title, company, location, source label, fit verdict badge, one-line summary, and primary action ("Open").

**"Worth a second look"** — jobs whose fit verdict has improved (because the user added a new GitHub repo, or because new context arrived). Smaller cards, less visual weight than the new section.

**"Watchlist activity"** — what's happened on watchlisted companies in the last week. New roles, hiring posts, news mentions if available.

If all three sections are empty (a quiet day), the screen says so plainly: "Nothing new. Take the day off." No filler, no fake activity, no "try these tips" content. Quiet days are real and the UI honors them.

### 4.2 Search

Two-column layout. Left column (320px): search form. Right column (fluid): results feed.

The search form lives left and stays sticky as the user scrolls results. Form fields:

- **Role** — text input with autocomplete from past searches.
- **Domain** — multi-select (e.g., "fintech," "developer tools," "AI/ML").
- **Locations** — multi-select chips with autocomplete. Mix country/state/city freely. India bias in autocomplete (Bengaluru, Mumbai, Hyderabad, Pune, Delhi, NCR, Remote-India top).
- **Work mode** — segmented control (Remote / Hybrid / On-site / Any).
- **Salary floor** — slider with INR/USD toggle.
- **Discovery modes** — three checkboxes for Mode 1/2/3, with cost/time hints next to each ("Aggregators · ~3 sec · free", "Founder posts · ~10 sec · ₹2", "Careers pages · 1-3 min · ₹5-15").

The results feed is a single column of job cards, sorted by fit verdict (strong → mismatch) then recency.

### 4.3 Job Card (used in feeds)

Compact, scannable. The card contains:

- **Top row:** title (largest text), company, source label as a small chip.
- **Second row:** location, work mode, salary if disclosed, posted date.
- **Fit verdict badge:** color-coded but with explicit text (`Strong fit · 9/10 skills present`). Never just a color or a single number.
- **Trust warning** (only when `verdict ∈ {suspicious, likely_scam}`): a small but prominent badge — amber for `suspicious`, red for `likely_scam` — with a short reason like "Requests payment up front" or "Reposted 8 times in 60 days." Verified and likely_real verdicts show **no badge** — the absence of a warning is the signal. This mirrors how Gmail handles "suspicious sender" alerts and prevents users from training themselves to ignore "✓ Verified" badges that appear everywhere.
- **One-line summary** generated by the fit-assessment prompt: "Strong domain match, but they want 7+ years and you have 4 — this is a stretch."
- **Knockout flags** (if any): small amber pills like "Requires US work auth · check before applying."
- **Primary action:** "Open" (full detail). Secondary: bookmark, hide.

Cards are ~120px tall (slightly taller when a trust warning is present). Hover reveals secondary actions; on touch, they're always visible.

### 4.4 Job Detail

Three columns when window is wide enough (≥1280px), stacks vertically below.

**Left (320px):** the job summary column.
- Title, company, full meta (location, mode, salary, posted, source link).
- Fit verdict full breakdown: skills present/missing in two columns; experience verdict; domain match; evidence strength; knockout-question warnings prominently displayed.
- Knockout-questions section: every detected knockout, with an honest "you can / can't / maybe" verdict per question based on the user's profile.
- **Trust breakdown** (only when `verdict ∈ {suspicious, likely_scam}`): a panel with the warning headline, a list of triggered scam signals with their rules, ghost-job signals if any, positive signals if any, and the AI-generated rationale paragraph. Includes a small "I trust this anyway" toggle that records the user's override without removing the warning entirely.

**Center (fluid):** the job description, rendered cleanly.

**Right (320px):** action panel.
- "Tailor resume" — primary action, large button.
- "Find contacts."
- "Prepare application package."
- "Mark as applied" / "Hide."
- Past application history if applicable.

### 4.5 Resume Tailoring

Three-pane, full-width. This is the most important screen in the product.

**Left pane (33%):** Original resume. Read-only. Sections collapsible.

**Center pane (34%):** The tailoring brief. Editable. Brief is rendered as a structured form, not raw JSON:
- Positioning (text area)
- Vocabulary shifts (key-value rows: "your phrase" → "JD's phrase")
- Keywords to add (chips, each with a check showing it's truthfully supported by the source)
- Keywords to omit (chips, each with the reason)
- Emphasis changes (text area)
- ATS family detected (read-only badge)
- Knockout warnings (read-only)
- Truthfulness boundaries (text area)

A "Generate brief" button at the top runs the meta-prompt; "Apply edits & generate resume" at the bottom runs the execution prompt.

**Right pane (33%):** The output. Two tabs: **Diff view** (changes from original highlighted in two-color diff) and **Final view** (clean rendered resume). Below, "Download DOCX," "Download PDF," "Save as new version."

A **fourth element** persistent at the top: a thin status bar showing "Brief: edited · Resume: not regenerated yet" — so the user knows when their changes need a regenerate.

### 4.6 Contact Discovery

Single page, two-column. Left: contact list. Right: contact detail.

Contact cards show: photo (if available from public source — never scraped from LinkedIn), name, role, tenure at company, relevance reason ("Likely the hiring manager for this role"), and contextual actions: Open LinkedIn (opens URL in new tab — manual visit), Draft outreach. **Copy email** appears as a fourth action only when a public email was incidentally discovered during signal aggregation, with the source shown on hover ("found on company About page"). When no email exists for the contact, the field and action are simply absent — the UI never shows "email unavailable" or similar negative space.

Contact detail panel (right) shows the personalization briefing, surfaced public signals (recent talks, GitHub activity, news mentions), and a "Draft outreach to this person" button.

### 4.7 Outreach Drafting

Modal or full-page (responsive). Single-column flow, top to bottom:

1. **Intent picker** at top: three options (Referral request / Application support / Cold introduction). Default selected based on contact role and whether the user has applied.

2. **Context preview** (collapsible): shows what data the meta-prompt has access to — your profile snapshot, the role, the contact's signal. Collapsible because most users won't need to read it but some will want to verify.

3. **Brief editor**: same pattern as resume tailoring — structured form, editable. Fields: hook, bridge, pitch, ask, tone, length budget, donts list.

4. **Generate**: one button.

5. **Draft + reasoning**: two-column. Draft on the left (editable text), reasoning on the right (read-only, explains why the AI made specific choices).

6. **Action row**: "Copy to clipboard," "Open in mail client," "Mark as sent." A "Humanize" button between Generate and Copy runs an optional second pass targeting AI-tells.

### 4.8 Applications

A simple table, not a kanban. Columns: company, role, status (applied / interview / offer / rejected / ghosted), applied-date, days-since, contact, resume version. Sort by any column. Filter by status.

A status-distribution sparkline at the top — small, not celebratory. "12 applied, 3 in interview, 1 offer, 2 rejected, 6 ghosted in the last 30 days." Honest, not gamified.

### 4.9 Watchlist

Simple list of companies. Each row: company name, careers URL, last-crawled timestamp, latest-job count delta ("3 new this week"). Click to expand and see the new jobs inline.

## 5. Visual System

### 5.1 Typography

Reject the genericisms. No Inter, no Roboto, no system-default Arial.

**Display / headings:** **Söhne** (paid) or **Geist** (free, by Vercel) — both have a confident, modern feel without being trendy.

**Body / UI:** **Geist** for everything if going single-family. Or pair Geist for headings with **iA Writer Quattro** for body if a slightly more editorial feel is wanted.

**Monospace** (for code, IDs, raw briefs in dev mode): **Geist Mono** or **JetBrains Mono**.

Sizes (mobile / desktop):
- H1: 24/32
- H2: 20/24
- H3: 16/20
- Body: 14/15
- Caption: 12/13
- All line-heights generous (1.5+ for body).

### 5.2 Color

A restrained palette with one accent.

**Light mode (default):**
- Background: `#FAFAF9` (warm off-white, not pure white)
- Surface: `#FFFFFF`
- Text primary: `#0A0A0A`
- Text secondary: `#737373`
- Border: `#E5E5E5`
- Accent: a single deep teal `#0F766E` used sparingly for primary actions and active states.

**Dark mode (toggle, not auto):**
- Background: `#0A0A0A`
- Surface: `#171717`
- Text primary: `#FAFAFA`
- Text secondary: `#A3A3A3`
- Border: `#262626`
- Accent: `#2DD4BF` (lighter teal for contrast)

**Semantic colors** for fit verdicts (used as backgrounds for badges with text labels — never color alone):
- Strong fit: `#15803D` on `#DCFCE7` (green)
- Good fit: `#1E40AF` on `#DBEAFE` (blue)
- Stretch: `#A16207` on `#FEF3C7` (amber)
- Below your level: `#525252` on `#F5F5F5` (neutral gray)
- Mismatch: `#B91C1C` on `#FEE2E2` (red)

That's it. No purples, no gradients, no neon accents. The accent is the only color the eye is drawn to.

### 5.3 Spacing

8px grid. Common gaps: 4, 8, 12, 16, 24, 32, 48, 64, 96.

Page max-widths:
- Today: 720px content
- Search results: full width
- Job detail: 1280px max
- Resume tailoring: full width

### 5.4 Iconography

**Phosphor Icons** (consistent, calm, two weights). Avoid icon-as-content; pair every icon with a text label except in highly compact toolbars.

### 5.5 Motion

Subtle, fast, purposeful.

- Page transitions: 150ms ease-out.
- Hover states: 100ms.
- Skeleton loading for AI-bound operations (brief generation, resume tailoring) with explicit progress signals — "Generating tailoring brief… 4-8 sec."
- No celebratory animations on action completion. A subtle "✓ Saved" toast is enough.
- Reduced-motion preference is respected globally (`prefers-reduced-motion`).

## 6. Interaction Patterns

### 6.1 Keyboard

The product is keyboard-first.

- `⌘K` opens command palette (search jobs, run actions, navigate).
- `⌘1-5` jumps to top-level routes.
- `j/k` for next/previous in feeds (Vim-style).
- `Enter` opens; `Esc` closes.
- `⌘Enter` submits forms.
- `?` shows the keyboard shortcut sheet.

### 6.2 Loading & AI States

AI calls have explicit, honest loading states:

- Loading message describes what's happening, not just "Loading…": *"Reading the JD…"*, *"Drafting tailoring brief…"*, *"Verifying truthfulness…"*
- Estimated time shown when known: *"~6 sec."*
- Cancel button always visible during long operations.
- On error, the error message is specific and actionable — never just "Something went wrong."

### 6.3 Empty States

Empty states tell the truth:
- Empty search results: "No jobs matched. Try broader locations or fewer filters."
- Empty Today feed: "Nothing new since your last visit."
- Empty applications table: "No applications yet. Find a job that fits and tailor a resume to start."

No "We couldn't find anything! Try our blog!" or other content that pads emptiness.

### 6.4 Confirmations

Destructive actions confirm; non-destructive actions don't.
- Delete a tailored resume version → confirm.
- Hide a job → no confirm (it's reversible).
- Mark as applied → no confirm (correctable).
- Wipe all data (admin) → typed confirmation ("type WIPE to continue").

### 6.5 Forms

Inline validation, not on-submit.
Error messages below fields, in red but not screaming.
Required fields are marked, optional fields are unmarked (not the inverse).
Disabled buttons explain why on hover/focus.

## 7. Accessibility

WCAG 2.2 AA minimum.
- All color contrasts checked.
- All interactive elements keyboard-reachable.
- Focus rings visible (don't `outline:none` without a replacement).
- Form fields have associated labels.
- Status messages use ARIA live regions.
- Verdict badges always include text, never color-only.
- The reduced-motion preference is honored.

## 8. Mobile

v1 is desktop-first. The web app is mobile-readable but not fully mobile-optimized.

What works on mobile in v1:
- Browsing the Today feed.
- Reading job details.
- Reading tailored resumes.

What is desktop-only in v1:
- Resume tailoring (three-pane layout).
- Contact discovery (two-pane layout).
- Outreach drafting beyond viewing.
- Browser extension (Chrome desktop).

If user demand emerges, mobile-first redesigns of the tailoring and outreach flows are a v2 candidate, not v1.

## 9. The "Calm UX" Litmus Test

Before shipping any UI element, the question to ask:

> Does this make the user feel a sense of urgency, accomplishment, or quantity?

If yes, reconsider. JobHunt is a slow, deliberate tool. Urgency, gamified accomplishment, and quantity-pressure are the marketing patterns of products that benefit from user volume. JobHunt benefits from user *outcomes*. The UX should reflect that.

The opposite question:

> Does this give the user honest, useful information that helps them decide what to do next?

If yes, ship it.

## 10. Cross-References

- Product scope: see **PRD.md**
- Technical mapping of these screens to components: see **Architecture.md § 5**
- Build order for screens: see **Plan.md** (each phase delivers specific screens)
- Component implementation rules: see **Agent.md § Coding Standards**
