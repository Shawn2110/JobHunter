from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.models import FitAssessment, Job, Profile, ProfileHandle, Resume

log = structlog.get_logger("app.ai.fit")


def _profile_payload(profile: Profile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "headline": profile.headline,
        "about_me_text": profile.about_me_text,
        "target_seniority": profile.target_seniority,
        "work_authorization": profile.work_authorization,
        "salary_floor": profile.salary_floor,
        "salary_currency": profile.salary_currency,
        "notice_period_days": profile.notice_period_days,
        "anti_preferences": profile.anti_preferences,
    }


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "work_mode": job.work_mode,
        "salary_text": job.salary_text,
        "description_md": job.description_md,
        "requirements_json": job.requirements_json,
        "ats_family": job.ats_family,
    }


async def _load_handle_signals(
    session: AsyncSession, profile_id: int
) -> dict[str, Any]:
    """Load handle signals via an explicit query rather than lazy access.

    The relationship is configured `lazy="selectin"`, but lazy loading
    breaks in async contexts when the parent isn't part of an active
    request — see SQLAlchemy MissingGreenlet. Querying explicitly side-
    steps that path entirely.
    """
    handles = (
        await session.execute(
            select(ProfileHandle).where(ProfileHandle.profile_id == profile_id)
        )
    ).scalars().all()
    return {h.kind: h.last_signal_json for h in handles if h.last_signal_json}


async def compute_fit_dict(
    *,
    profile_payload: dict[str, Any],
    resume_json: dict[str, Any],
    handle_signals: dict[str, Any],
    job_payload: dict[str, Any],
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Stateless fit assessment.

    Renders the meta-prompt, calls Claude, validates output against
    the manifest's schema, and returns the parsed dict. No DB writes.

    Used by the extension's live-preview score endpoint where we
    don't want to persist a FitAssessment for a job the user might
    immediately close. `assess_fit` (below) is the persisting wrapper.
    """
    rendered = loader.render(
        "meta",
        "fit_assessment_brief",
        {
            "profile": profile_payload,
            "resume_json": resume_json,
            "handle_signals": handle_signals,
            "job": job_payload,
        },
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )
    return parsed


async def assess_fit(
    job: Job,
    profile: Profile,
    resume: Resume | None,
    *,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
) -> FitAssessment:
    """Run the fit_assessment_brief meta-prompt and persist the verdict.

    Upserts on job_id (unique constraint) — re-running replaces the
    previous assessment.
    """
    handle_signals = await _load_handle_signals(session, profile.id)
    parsed = await compute_fit_dict(
        profile_payload=_profile_payload(profile),
        resume_json=(resume.parsed_json if resume else {}),
        handle_signals=handle_signals,
        job_payload=_job_payload(job),
        claude=claude,
        loader=loader,
        session=session,
    )

    existing = (
        await session.execute(
            select(FitAssessment).where(FitAssessment.job_id == job.id)
        )
    ).scalar_one_or_none()

    fields = dict(
        skills_match_json=parsed["skills_match"],
        experience_verdict=parsed["experience_verdict"],
        domain_match=parsed["domain_match"],
        evidence_strength=parsed["evidence_strength"],
        knockout_risks_json=parsed["knockout_risks"],
        verdict=parsed["verdict"],
        summary_md=parsed["summary_md"],
    )

    if existing is None:
        assessment = FitAssessment(job_id=job.id, **fields)
        session.add(assessment)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        assessment = existing

    await session.commit()
    await session.refresh(assessment)
    log.info(
        "fit.assessed",
        job_id=job.id,
        verdict=assessment.verdict,
    )
    return assessment


async def load_handle_signals(
    session: AsyncSession, profile_id: int
) -> dict[str, Any]:
    """Public re-export of the handle-signals loader for stateless callers."""
    return await _load_handle_signals(session, profile_id)


def profile_payload(profile: Profile) -> dict[str, Any]:
    """Public re-export — used by extension scoring."""
    return _profile_payload(profile)
