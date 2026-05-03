from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.models import Job, Profile, Resume, TailoredArtifact, TailoringBrief
from app.services.cover_letter import generate_cover_letter

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPTS_DIR = REPO_ROOT / "prompts"


_FAKE_BRIEF = {
    "opener_angle": "Your 2024 launch of payment APIs solves the problem I built X to address.",
    "narrative_arc": "Three sentences mapping experience to role.",
    "closing_cta": "Open to a 30-min chat to share specifics.",
    "tone": "warm-direct",
    "length_target_words": 240,
    "donts": ["I am writing to apply", "leverage", "synergy"],
}

_FAKE_LETTER = {
    "body_md": "Your 2024 launch of payment APIs caught my attention because I built a similar system at Acme that handled 10M req/day.\n\nAt Acme I led the migration from PostgreSQL 13 to 15 with zero downtime — exactly the kind of low-disruption infra work your team is hiring for.\n\nWould love a 30-min chat to share specifics about my experience with high-throughput systems.",
    "word_count": 62,
    "reasoning_md": "Led with a concrete product reference (their 2024 launch); bridged to one specific bullet from the resume; small clear ask.",
}


@pytest.mark.asyncio
async def test_generate_cover_letter_persists_brief_and_artifact(
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # First Claude call returns the brief, second returns the letter.
    # _FakeMessages always returns the same response; we change it
    # between calls by replacing the .text on the response object.
    response = frozen_claude._fake_messages.response  # type: ignore[attr-defined]
    response.content[0].text = json.dumps(_FAKE_BRIEF)

    fake_messages = frozen_claude._fake_messages  # type: ignore[attr-defined]

    original_create = fake_messages.create
    call_count = {"n": 0}

    async def staged_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            response.content[0].text = json.dumps(_FAKE_BRIEF)
        else:
            response.content[0].text = json.dumps(_FAKE_LETTER)
        return await original_create(**kwargs)

    monkeypatch.setattr(fake_messages, "create", staged_create)

    profile = Profile(name="U", target_seniority="senior")
    db_session.add(profile)
    resume = Resume(
        version=1,
        is_master=True,
        parsed_json={
            "name": "U",
            "skills": ["Python", "PostgreSQL"],
            "experience": [
                {
                    "company": "Acme",
                    "title": "Senior Engineer",
                    "bullets": ["Led PostgreSQL migration"],
                }
            ],
        },
    )
    db_session.add(resume)
    job = Job(
        title="Senior Backend Engineer",
        company="Razorpay",
        company_canonical="razorpay",
        description_md="Build payment infrastructure used by 10M+ businesses.",
    )
    db_session.add(job)
    await db_session.commit()

    loader = PromptLoader(PROMPTS_DIR)
    brief, artifact = await generate_cover_letter(
        job=job,
        profile=profile,
        base_resume=resume,
        claude=frozen_claude,
        loader=loader,
        session=db_session,
    )

    assert brief.kind == "cover_letter"
    assert brief.brief_json["opener_angle"].startswith("Your 2024 launch")
    assert brief.executed_at is not None

    assert artifact.kind == "cover_letter"
    assert artifact.job_id == job.id
    assert artifact.brief_id == brief.id
    assert artifact.content_md is not None
    assert "Your 2024 launch" in artifact.content_md
    assert artifact.content_json is not None
    assert artifact.content_json["word_count"] == 62
    assert "reasoning_md" in artifact.content_json


@pytest.mark.asyncio
async def test_cover_letter_brief_kind_is_distinguishable(
    db_session: AsyncSession,
    frozen_claude: ClaudeClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both resume-tailoring and cover-letter briefs land in the
    same table; `kind` is what tells them apart."""
    response = frozen_claude._fake_messages.response  # type: ignore[attr-defined]
    fake_messages = frozen_claude._fake_messages  # type: ignore[attr-defined]
    original_create = fake_messages.create
    call_count = {"n": 0}

    async def staged_create(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            response.content[0].text = json.dumps(_FAKE_BRIEF)
        else:
            response.content[0].text = json.dumps(_FAKE_LETTER)
        return await original_create(**kwargs)

    monkeypatch.setattr(fake_messages, "create", staged_create)

    profile = Profile(name="U")
    db_session.add(profile)
    resume = Resume(version=1, is_master=True, parsed_json={"name": "U"})
    db_session.add(resume)
    job = Job(title="t", company="c", company_canonical="c")
    db_session.add(job)
    await db_session.commit()

    loader = PromptLoader(PROMPTS_DIR)
    brief, _ = await generate_cover_letter(
        job=job,
        profile=profile,
        base_resume=resume,
        claude=frozen_claude,
        loader=loader,
        session=db_session,
    )

    rows = (
        await db_session.execute(
            select(TailoringBrief).where(TailoringBrief.kind == "cover_letter")
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == brief.id
