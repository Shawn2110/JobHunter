from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.models import Job, TrustAssessment
from app.trust.ai_check import ai_trust_check
from app.trust.longitudinal import evaluate_longitudinal, record_sighting
from app.trust.rules import evaluate_text, static_check_score
from app.trust.verdict import compose_verdict

log = structlog.get_logger("app.trust.service")


async def assess_trust(
    job: Job,
    *,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
    locale: str = "global",
    company_context: dict[str, Any] | None = None,
) -> TrustAssessment:
    """End-to-end trust assessment for one Job.

    Runs Layer A (rules), Layer B (AI), Layer C (longitudinal),
    composes a final verdict, persists/upserts a TrustAssessment row,
    and records a JobRepostHistory sighting.
    """
    # ── Layer A: rules ──
    text = " ".join(filter(None, [job.title, job.description_md or ""]))
    rule_hits = evaluate_text(text, locale=locale)  # type: ignore[arg-type]
    static_score = static_check_score(rule_hits)

    # ── Layer B: AI ──
    ai_result = await ai_trust_check(
        job_title=job.title,
        company=job.company,
        job_description=job.description_md or "",
        rule_hits=rule_hits,
        company_context=company_context,
        claude=claude,
        loader=loader,
        session=session,
    )

    # ── Layer C: longitudinal ──
    # Record this sighting first so the next assessment sees it
    await record_sighting(
        company=job.company,
        title=job.title,
        description=job.description_md,
        source_url=job.apply_url,
        session=session,
    )
    long_signals, long_score = await evaluate_longitudinal(
        company=job.company,
        title=job.title,
        description=job.description_md,
        session=session,
    )

    # ── Compose ──
    composed = compose_verdict(
        rule_hits=rule_hits,
        ai_result=ai_result,
        longitudinal_signals=long_signals,
    )

    # ── Persist (upsert on job_id) ──
    existing = (
        await session.execute(
            select(TrustAssessment).where(TrustAssessment.job_id == job.id)
        )
    ).scalar_one_or_none()

    fields = dict(
        verdict=composed.verdict,
        scam_signals_json=composed.scam_signals,
        ghost_job_signals_json=composed.ghost_job_signals,
        positive_signals_json=composed.positive_signals,
        rationale_md=composed.rationale_md,
        static_check_score=static_score,
        ai_check_score=ai_result.get("ai_check_score"),
        longitudinal_score=long_score,
    )

    if existing is None:
        assessment = TrustAssessment(job_id=job.id, **fields)
        session.add(assessment)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        assessment = existing

    await session.commit()
    await session.refresh(assessment)
    log.info(
        "trust.assessed",
        job_id=job.id,
        verdict=composed.verdict,
        static=static_score,
        ai=ai_result.get("ai_check_score"),
        longitudinal=long_score,
    )
    return assessment
