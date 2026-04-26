from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.fit import assess_fit
from app.ai.prompt_loader import PromptLoader
from app.models import Job, Profile, Resume

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


@pytest.mark.asyncio
async def test_assess_fit_persists_verdict(
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_brief = {
        "skills_match": {
            "present": ["Python", "FastAPI"],
            "missing": ["Kubernetes"],
            "score_required": "2/3",
        },
        "experience_verdict": "They want 4-7 years; you have 4. Good fit.",
        "domain_match": "Strong — fintech experience matches.",
        "evidence_strength": "Top GitHub repo (Python, 200 stars) maps to their stack.",
        "knockout_risks": [
            {
                "question": "Are you authorized to work in India?",
                "criterion": "in_authorization",
                "user_status": "Indian citizen",
                "can_pass": "yes",
            }
        ],
        "verdict": "good",
        "summary_md": "Strong skills overlap, no knockouts, slight gap on K8s.",
    }
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps(fake_brief),
    )

    profile = Profile(name="U", target_seniority="senior")
    db_session.add(profile)
    await db_session.commit()

    resume = Resume(
        version=1,
        is_master=True,
        parsed_json={"name": "U", "skills": ["Python", "FastAPI"]},
    )
    db_session.add(resume)

    job = Job(
        title="Senior Python Engineer",
        company="Acme",
        company_canonical="acme",
        description_md="Looking for 4-7 yrs Python, FastAPI, Kubernetes",
    )
    db_session.add(job)
    await db_session.commit()

    loader = PromptLoader(PROMPTS_DIR)
    fit = await assess_fit(
        job, profile, resume, claude=frozen_claude, loader=loader, session=db_session
    )

    assert fit.verdict == "good"
    assert fit.skills_match_json == fake_brief["skills_match"]
    assert len(fit.knockout_risks_json or []) == 1


@pytest.mark.asyncio
async def test_assess_fit_upserts_existing(
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        frozen_claude._fake_messages.response.content[0],  # type: ignore[attr-defined]
        "text",
        json.dumps({
            "skills_match": {"present": [], "missing": [], "score_required": None},
            "experience_verdict": "x",
            "domain_match": "x",
            "evidence_strength": "x",
            "knockout_risks": [],
            "verdict": "stretch",
            "summary_md": "x",
        }),
    )

    profile = Profile(name="U")
    db_session.add(profile)
    job = Job(title="t", company="c", company_canonical="c")
    db_session.add(job)
    await db_session.commit()

    loader = PromptLoader(PROMPTS_DIR)
    fit1 = await assess_fit(
        job, profile, None, claude=frozen_claude, loader=loader, session=db_session
    )
    fit2 = await assess_fit(
        job, profile, None, claude=frozen_claude, loader=loader, session=db_session
    )
    # Same row updated, not duplicated
    assert fit1.id == fit2.id
