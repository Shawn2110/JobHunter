from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader

log = structlog.get_logger("app.ai.knockouts")


async def extract_knockouts(
    job_title: str,
    job_description: str,
    *,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """Run the extract_knockouts static prompt and return the parsed list."""
    if not job_description.strip():
        return []
    rendered = loader.render(
        "static",
        "extract_knockouts",
        {"job_title": job_title, "job_description": job_description},
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )
    knockouts = parsed.get("knockouts", [])
    log.info("knockouts.extracted", title=job_title, count=len(knockouts))
    return knockouts
