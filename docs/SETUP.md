# JobHunt — Setup

JobHunt is single-user and self-hosted. The fast path is Docker
Compose; the local-dev path uses your system Python + Node directly.

---

## 1. Clone and configure

```bash
git clone https://github.com/Shawn2110/JobHunter.git
cd JobHunter
cp .env.example .env
```

Or run the interactive setup CLI:

```bash
python scripts/setup_ai.py
```

It writes `ANTHROPIC_API_KEY` into `.env` (the only required key)
and leaves all other settings at their defaults.

**Discovery sources are keyless** — Greenhouse, Lever, and Ashby
publish public board APIs the system uses directly; Reddit's JSON
API powers founder-post discovery. You don't need a job-aggregator
subscription to use JobHunt. See [ADR 0005](decisions/0005-drop-aggregators-keyless-ats.md)
for the rationale.

Optional keys you can add later in `.env`:

- **`BRAVE_SEARCH_API_KEY` or `SERPER_API_KEY`** — enables Phase 6
  contact discovery (returns `linkedin.com/in` URLs the user clicks
  manually; JobHunt never fetches LinkedIn pages itself).
- **`GITHUB_TOKEN`** — raises GitHub's rate limit from 60 → 5000 req/hr
  for handle signal fetches.
- **`FIRECRAWL_API_KEY`** — would let the careers crawler handle SPA
  pages (Naukri, Foundit, Wellfound). Not currently wired in; the
  default keyless path covers Greenhouse / Lever / Ashby plus any
  company-direct careers page that ships JSON-LD.

## 2. Run with Docker (recommended)

```bash
docker compose up
```

This brings up three services:
- `backend` on `localhost:8000`
- `frontend` on `localhost:3000`
- `worker` (APScheduler) for nightly watchlist crawls

Visit `http://localhost:3000`. The home screen shows backend
connectivity + which providers your `.env` has filled in.

## 3. Run without Docker (local dev)

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # macOS / Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # localhost:3000
```

### Worker (optional)

```bash
cd backend
.venv/Scripts/python -m app.workers.runner
```

## 4. First-run flow

1. Open `http://localhost:3000/profile`. Fill in name, headline,
   handles (URLs only — JobHunt never logs into LinkedIn for you),
   compensation. Save.
2. Upload your master resume (PDF or DOCX). The parser turns it into
   structured JSON and stores it as v1.
3. Open `/search`, run a query. Adjust filters, mode toggles.
4. Open any job → "Tailor resume" produces a Layer-1 brief. Edit it.
   "Generate" produces the rewritten resume.
5. Apply via the ATS page. The browser extension autofills standard
   fields. **You click submit.**

## 5. Browser extension

Load unpacked from `extension/`:
1. Visit `chrome://extensions`.
2. Enable Developer Mode.
3. "Load unpacked" → select the `extension/` folder.
4. Visit any Greenhouse / Lever / Workday / Ashby / iCIMS /
   SmartRecruiters page; the JobHunt action bar appears in the
   bottom-right.

The extension only ever talks to `localhost:8000`. Never auto-submits.

## 6. Keeping it updated

```bash
git pull
# Docker:
docker compose up --build -d
# Local:
cd backend && python -m alembic upgrade head
cd ../frontend && npm install
```

## 7. Exporting / wiping your data

Everything lives in `data/jobhunt.db` and `data/resumes/`. To export:

```bash
curl http://localhost:8000/admin/export > backup.json
```

To wipe everything (typed confirmation required):

```bash
curl -X POST http://localhost:8000/admin/wipe \
  -H 'Content-Type: application/json' \
  -d '{"confirmation": "WIPE"}'
```

---

For deployment beyond your laptop, see [DEPLOYMENT.md](DEPLOYMENT.md).
For what JobHunt is and isn't, see [PRD.md](PRD.md).
