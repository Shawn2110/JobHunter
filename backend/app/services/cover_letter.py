from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.models import (
    Job,
    Profile,
    Resume,
    TailoredArtifact,
    TailoringBrief,
)

log = structlog.get_logger("app.services.cover_letter")


def _profile_payload(profile: Profile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "headline": profile.headline,
        "about_me_text": profile.about_me_text,
        "target_seniority": profile.target_seniority,
        "anti_preferences": profile.anti_preferences,
    }


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description_md": job.description_md,
        "ats_family": job.ats_family,
    }


async def generate_cover_letter(
    *,
    job: Job,
    profile: Profile,
    base_resume: Resume,
    contact: dict[str, Any] | None = None,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
) -> tuple[TailoringBrief, TailoredArtifact]:
    """One-shot cover-letter generation.

    Runs Layer-1 (brief) → Layer-2 (execution) inline. No
    user-edits-the-brief workflow today; if needed later, split into
    two endpoints mirroring the resume tailoring flow.
    """
    contact = contact or {}

    # ── Layer 1: brief ──
    rendered_brief = loader.render(
        "meta",
        "cover_letter_brief",
        {
            "profile": _profile_payload(profile),
            "resume_json": base_resume.parsed_json or {},
            "job": _job_payload(job),
            "contact": contact,
        },
    )
    brief_payload, _ = await claude.complete_json(
        rendered_brief, loader=loader, session=session
    )

    brief_row = TailoringBrief(
        job_id=job.id,
        base_resume_id=base_resume.id,
        kind="cover_letter",
        brief_json=brief_payload,
    )
    session.add(brief_row)
    await session.flush()  # get brief_row.id

    # ── Layer 2: execution ──
    rendered_exec = loader.render(
        "execution",
        "cover_letter",
        {
            "brief": brief_payload,
            "resume_json": base_resume.parsed_json or {},
            "job": _job_payload(job),
            "contact": contact,
        },
    )
    parsed, _ = await claude.complete_json(
        rendered_exec, loader=loader, session=session
    )

    artifact = TailoredArtifact(
        job_id=job.id,
        brief_id=brief_row.id,
        kind="cover_letter",
        content_md=parsed.get("body_md"),
        content_json={
            "word_count": parsed.get("word_count"),
            "reasoning_md": parsed.get("reasoning_md"),
            "brief": brief_payload,
        },
    )
    session.add(artifact)

    brief_row.executed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(brief_row)
    await session.refresh(artifact)

    log.info(
        "cover_letter.generated",
        job_id=job.id,
        artifact_id=artifact.id,
        word_count=parsed.get("word_count"),
    )
    return brief_row, artifact
