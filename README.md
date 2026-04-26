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

Pre-flight (Phase 0). See [docs/Plan.md § 2](docs/Plan.md) for the active task.

## Getting started

> The project is currently being scaffolded. Setup instructions land with
> Phase 10's [docs/SETUP.md](docs/Plan.md). Until then, the short version is:

```bash
git clone https://github.com/Shawn2110/JobHunter.git
cd JobHunter
cp .env.example .env
# Fill in only the keys for the providers you want to use.
docker compose up
```

## License

To be decided. Until a license file is added, all rights reserved.
