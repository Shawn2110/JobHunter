"""Background-tailor worker for the v2 extension save-and-tailor flow.

When the user clicks 'Save & tailor' in the in-page overlay, the
endpoint persists the Job and schedules `tailor_job_in_background`
via `asyncio.create_task`. The user can immediately go back to
browsing the next job; meanwhile this worker generates resume +
cover letter + custom-question answers in sequence. The package
page polls for new artifacts and renders them as they arrive.

This worker:
- Opens its own SessionLocal (the request session has closed by now)
- Loads job + profile + master resume; logs and returns if any
  is missing (no panic, just a no-op)
- Instantiates ClaudeClient directly from settings (the FastAPI
  dependency injection isn't available outside a request)
- Runs each tailoring task in a try/except so one failure doesn't
  starve the others
- Logs every outcome via structlog
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import desc, select

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.config import REPO_ROOT, settings
from app.db import SessionLocal
from app.models import Job, Profile, Resume, TailoredArtifact
from app.services.cover_letter import generate_cover_letter
from app.services.custom_questions import generate_custom_answers
from app.services.tailoring import execute_tailoring, generate_brief

log = structlog.get_logger("app.workers.background_tailor")


def _build_claude() -> ClaudeClient | None:
    """Return a ClaudeClient when an API key is configured, else None.

    Mirrors `app.deps._get_claude_client` but doesn't raise — the
    background path needs to log-and-return on misconfig, not 503."""
    if not settings.anthropic_api_key:
        return None
    return ClaudeClient(
        api_key=settings.anthropic_api_key,
        default_model=settings.anthropic_model_default,
        high_stakes_model=settings.anthropic_model_high_stakes,
    )


async def tailor_job_in_background(job_id: int) -> None:
    """End-to-end tailoring for one Job. Runs resume → cover letter →
    custom answers sequentially in a single session. Each task is
    independent — one failing doesn't block the others.

    Total wall time: ~60-120 seconds depending on Claude latency.
    """
    try:
        async with SessionLocal() as session:
            job = await session.get(Job, job_id)
            profile = (
                await session.execute(select(Profile).limit(1))
            ).scalar_one_or_none()
            base_resume = (
                await session.execute(
                    select(Resume)
                    .where(Resume.is_master.is_(True))
                    .order_by(desc(Resume.version))
                    .limit(1)
                )
            ).scalar_one_or_none()

            if job is None:
                log.warning("background_tailor.skipped", reason="no_job", job_id=job_id)
                return
            if profile is None:
                log.warning(
                    "background_tailor.skipped",
                    reason="no_profile",
                    job_id=job_id,
                )
                return
            if base_resume is None:
                log.warning(
                    "background_tailor.skipped",
                    reason="no_master_resume",
                    job_id=job_id,
                )
                return

            claude = _build_claude()
            if claude is None:
                log.warning(
                    "background_tailor.skipped",
                    reason="anthropic_key_missing",
                    job_id=job_id,
                )
                return

            loader = PromptLoader(prompts_dir=REPO_ROOT / "prompts")

            log.info("background_tailor.start", job_id=job_id)

            # ── Resume tailoring ────────────────────────────────────
            try:
                brief = await generate_brief(
                    job=job,
                    profile=profile,
                    base_resume=base_resume,
                    claude=claude,
                    loader=loader,
                    session=session,
                )
                await execute_tailoring(
                    brief=brief,
                    base_resume=base_resume,
                    job=job,
                    claude=claude,
                    loader=loader,
                    session=session,
                )
                log.info(
                    "background_tailor.resume_done", job_id=job_id, brief_id=brief.id
                )
            except Exception as e:  # noqa: BLE001
                log.error(
                    "background_tailor.resume_failed",
                    job_id=job_id,
                    error=type(e).__name__,
                    detail=str(e)[:300],
                )

            # ── Cover letter ────────────────────────────────────────
            try:
                await generate_cover_letter(
                    job=job,
                    profile=profile,
                    base_resume=base_resume,
                    claude=claude,
                    loader=loader,
                    session=session,
                )
                log.info("background_tailor.cover_letter_done", job_id=job_id)
            except Exception as e:  # noqa: BLE001
                log.error(
                    "background_tailor.cover_letter_failed",
                    job_id=job_id,
                    error=type(e).__name__,
                    detail=str(e)[:300],
                )

            # ── Custom-question answers ─────────────────────────────
            try:
                profile_payload: dict[str, Any] = {
                    "name": profile.name,
                    "headline": profile.headline,
                    "about_me_text": profile.about_me_text,
                    "target_seniority": profile.target_seniority,
                    "salary_floor": profile.salary_floor,
                    "salary_currency": profile.salary_currency,
                    "notice_period_days": profile.notice_period_days,
                }
                job_payload: dict[str, Any] = {
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "description_md": job.description_md,
                    "salary_text": job.salary_text,
                }
                answers = await generate_custom_answers(
                    profile_payload=profile_payload,
                    resume_json=base_resume.parsed_json or {},
                    job_payload=job_payload,
                    keys=None,
                    claude=claude,
                    loader=loader,
                    session=session,
                )
                artifact = TailoredArtifact(
                    job_id=job.id,
                    kind="custom_answers",
                    content_json={
                        "answers": [
                            {
                                "key": a.key,
                                "question": a.question,
                                "answer_md": a.answer_md,
                                "word_count": a.word_count,
                            }
                            for a in answers
                        ]
                    },
                    content_md="\n\n---\n\n".join(
                        f"### {a.question}\n\n{a.answer_md}" for a in answers
                    ),
                )
                session.add(artifact)
                await session.commit()
                log.info(
                    "background_tailor.custom_answers_done",
                    job_id=job_id,
                    count=len(answers),
                )
            except Exception as e:  # noqa: BLE001
                log.error(
                    "background_tailor.custom_answers_failed",
                    job_id=job_id,
                    error=type(e).__name__,
                    detail=str(e)[:300],
                )

            log.info("background_tailor.complete", job_id=job_id)
    except Exception as e:  # noqa: BLE001
        log.error(
            "background_tailor.fatal",
            job_id=job_id,
            error=type(e).__name__,
            detail=str(e)[:300],
        )
