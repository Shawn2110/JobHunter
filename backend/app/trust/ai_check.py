from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.trust.rules import RuleHit

log = structlog.get_logger("app.trust.ai_check")


async def ai_trust_check(
    *,
    job_title: str,
    company: str,
    job_description: str,
    rule_hits: list[RuleHit],
    company_context: dict[str, Any] | None,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    """Run Layer-B AI trust assessment.

    Returns the parsed dict (verdict, additional_signals_found,
    ai_check_score, rationale_md). Caller composes the final verdict
    from this plus Layer A and Layer C in verdict.py.
    """
    rendered = loader.render(
        "static",
        "trust_assessment",
        {
            "job_title": job_title,
            "company": company,
            "job_description": job_description,
            "rule_hits": [
                {
                    "id": h.id,
                    "severity": h.severity,
                    "description": h.description,
                }
                for h in rule_hits
            ],
            "company_context": company_context or {},
        },
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )
    log.info(
        "trust.ai_check",
        company=company,
        verdict=parsed.get("verdict"),
        score=parsed.get("ai_check_score"),
    )
    return parsed
