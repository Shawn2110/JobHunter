from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.knockouts import extract_knockouts
from app.ai.prompt_loader import PromptError, PromptLoader
from app.ai.truthfulness_check import check_truthfulness
from app.models import (
    Job,
    Profile,
    Resume,
    TailoredArtifact,
    TailoringBrief,
)

log = structlog.get_logger("app.services.tailoring")


class TailoringError(Exception):
    """Raised when tailoring fails after retry."""


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
        "requirements_json": job.requirements_json,
    }


async def generate_brief(
    *,
    job: Job,
    profile: Profile,
    base_resume: Resume,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
) -> TailoringBrief:
    """Layer 1 — produce the editable tailoring brief."""
    knockouts = await extract_knockouts(
        job_title=job.title,
        job_description=job.description_md or "",
        claude=claude,
        loader=loader,
        session=session,
    )

    rendered = loader.render(
        "meta",
        "resume_tailoring_brief",
        {
            "profile": _profile_payload(profile),
            "resume_json": base_resume.parsed_json or {},
            "job": _job_payload(job),
            "knockouts": knockouts,
        },
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )

    brief = TailoringBrief(
        job_id=job.id,
        base_resume_id=base_resume.id,
        brief_json=parsed,
    )
    session.add(brief)
    await session.commit()
    await session.refresh(brief)
    log.info("tailoring.brief_generated", brief_id=brief.id, job_id=job.id)
    return brief


async def execute_tailoring(
    *,
    brief: TailoringBrief,
    base_resume: Resume,
    job: Job,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
    max_retries: int = 1,
) -> TailoredArtifact:
    """Layer 2 — produce the rewritten resume, validate truthfulness,
    persist as a TailoredArtifact.

    On truthfulness failure, retries once. After max_retries the
    artifact is still persisted with truthfulness_passed=False so the
    user can see what failed.
    """
    effective_brief = brief.user_edits_json or brief.brief_json
    output: dict[str, Any] | None = None
    report = None

    for attempt in range(max_retries + 1):
        rendered = loader.render(
            "execution",
            "resume_rewrite",
            {
                "brief": effective_brief,
                "resume_json": base_resume.parsed_json or {},
                "job": _job_payload(job),
            },
        )
        try:
            parsed, _ = await claude.complete_json(
                rendered, loader=loader, session=session
            )
        except PromptError as e:
            if attempt < max_retries:
                log.warning("tailoring.retry", error=str(e))
                continue
            raise TailoringError(f"Layer-2 produced invalid JSON: {e}") from e

        report = check_truthfulness(
            source_resume=base_resume.parsed_json or {},
            output_resume=parsed,
            brief=effective_brief,
        )
        output = parsed
        if report.passed:
            break
        log.warning(
            "tailoring.truthfulness_violation",
            attempt=attempt,
            violations=report.violations,
        )

    if output is None:
        raise TailoringError("Layer-2 produced no output")

    artifact = TailoredArtifact(
        job_id=job.id,
        brief_id=brief.id,
        kind="resume",
        content_json=output,
        truthfulness_passed=bool(report and report.passed),
        truthfulness_violations_json=(
            report.violations if report and not report.passed else None
        ),
    )
    session.add(artifact)
    brief.executed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(artifact)
    log.info(
        "tailoring.executed",
        artifact_id=artifact.id,
        brief_id=brief.id,
        truthfulness_passed=artifact.truthfulness_passed,
    )
    return artifact
