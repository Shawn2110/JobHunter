# JobHunt

An open-source, self-hosted, single-user, AI-augmented job-hunting system.
Optimizes for **quality of applications, not quantity** — built around a
meta-prompt → execution-prompt AI pattern where the user always sees and
edits the AI's brief before any output is produced.

> **JobHunt is not an auto-apply tool.** It is not a LinkedIn automation
> tool. It is not a SaaS. It runs on your machine, with your API keys, on
> your data.

---

## What it does

- **Discovery** across job aggregators, founder posts, and company careers
  pages — merged into one feed.
- **Multi-dimensional fit assessment** with an honest verdict
  (`strong / good / stretch / below / mismatch`), not a single inflated score.
- **Trust assessment** — flags scams and ghost jobs without ever
  auto-hiding listings.
- **Resume tailoring** via a two-layer meta-prompt you can read and edit
  before any rewriting happens.
- **Contact discovery** through public sources only — no LinkedIn scraping,
  no paid email-finder services.
- **Outreach drafting** that you copy and send manually.
- **Application packaging** with a browser extension that autofills forms.
  You always click submit.

For the full product scope and rationale, see [docs/PRD.md](docs/PRD.md).

## Documentation

| Document | Purpose |
| --- | --- |
| [docs/PRD.md](docs/PRD.md) | Product scope, behavior principles, anti-patterns |
| [docs/Architecture.md](docs/Architecture.md) | Tech stack, data model, services, deployment |
| [docs/Plan.md](docs/Plan.md) | Phased build sequence and current task pointer |
| [docs/Agent.md](docs/Agent.md) | Coding standards and hard refusals for AI agents |
| [docs/Design.md](docs/Design.md) | UI/UX direction |

## Status

Active development. Current focus: v1 extension features (autofill +
rich save). v2 surfaces (in-page scoring overlay, background tailor)
are wired up and tested, but not the priority. Architecture notes in
[docs/decisions/0007-v2-wave-1-extension-primary.md](docs/decisions/0007-v2-wave-1-extension-primary.md).

## Install the browser extension

The extension runs alongside any supported job board (Greenhouse, Lever,
Ashby, Workday, iCIMS, SmartRecruiters, Naukri, Foundit, Wellfound) and
gives you:

- **One-click save** of the current job posting via the toolbar popup
- **Autofill** for application forms (name, email, phone, links,
  summary) — pulled from your local profile + master resume
- **In-page score overlay** with fit / trust / knockouts (optional, v2)

The extension never auto-submits. It only talks to your local backend
on `http://localhost:8000`.

**Download:**
[`release/jobhunt-extension-0.1.0.zip`](release/jobhunt-extension-0.1.0.zip)
([raw](https://github.com/Shawn2110/JobHunter/raw/main/release/jobhunt-extension-0.1.0.zip))

**Load it into Chrome / Edge / Brave:**

1. Download the zip above and extract it to any folder.
2. Open `chrome://extensions` (or `edge://extensions`, `brave://extensions`).
3. Toggle **Developer mode** on (top-right).
4. Click **Load unpacked** and select the extracted folder.
5. Make sure the JobHunt backend is running on `http://localhost:8000`
   (see *Run the backend* below). The extension only talks to your local
   machine — no data leaves your laptop.

> The zip is built straight from `extension/` in this repo — if you'd
> rather not download, you can `Load unpacked` directly from
> `extension/` after cloning. To rebuild the zip yourself:
> `python scripts/build_extension.py`.

## Run the backend

```bash
git clone https://github.com/Shawn2110/JobHunter.git
cd JobHunter
cp .env.example .env
# Optional: add ANTHROPIC_API_KEY to .env to enable AI tailoring.
# Without it, save-and-tailor still saves jobs but skips generation.
docker compose up
```

Or, for local development without Docker:

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate    # Windows: .\.venv\Scripts\activate
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

The web app (optional review canvas) lives in `frontend/`:

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## License

To be decided. Until a license file is added, all rights reserved.
