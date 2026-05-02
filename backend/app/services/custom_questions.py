from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader

log = structlog.get_logger("app.services.custom_questions")

# Order is the order shown in the UI checklist.
COMMON_QUESTIONS: list[tuple[str, str]] = [
    ("why_this_company", "Why this company?"),
    ("why_this_role", "Why this role?"),
    ("why_leaving", "Why are you leaving / why did you leave your last role?"),
    ("biggest_project", "Tell us about a difficult or impactful project."),
    ("salary_expectations", "What are your salary expectations?"),
]


@dataclass(frozen=True)
class CustomAnswer:
    key: str
    question: str
    answer_md: str
    word_count: int


async def generate_custom_answers(
    *,
    profile_payload: dict[str, Any],
    resume_json: dict[str, Any],
    job_payload: dict[str, Any],
    keys: list[str] | None = None,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession | None = None,
) -> list[CustomAnswer]:
    """Generate answers for the requested custom questions.

    `keys` defaults to all entries in COMMON_QUESTIONS. Each prompt
    lives at prompts/static/custom_questions/<key>.md and is responsible
    for its own input shape — we pass profile / resume / job to all of
    them; prompts that only declare a subset of inputs will fail
    validation, which is the correct behavior.
    """
    selected = keys or [k for k, _ in COMMON_QUESTIONS]
    out: list[CustomAnswer] = []
    questions_by_key = dict(COMMON_QUESTIONS)

    for key in selected:
        if key not in questions_by_key:
            log.warning("custom_questions.unknown_key", key=key)
            continue

        manifest_inputs: dict[str, Any] = {}
        # Build the input set the prompt declares
        loaded = loader.load("static", f"custom_questions/{key}")
        declared = {i.name for i in loaded.manifest.inputs}
        if "profile" in declared:
            manifest_inputs["profile"] = profile_payload
        if "resume_json" in declared:
            manifest_inputs["resume_json"] = resume_json
        if "job" in declared:
            manifest_inputs["job"] = job_payload

        rendered = loader.render(
            "static", f"custom_questions/{key}", manifest_inputs
        )
        parsed, _ = await claude.complete_json(
            rendered, loader=loader, session=session
        )
        out.append(
            CustomAnswer(
                key=key,
                question=questions_by_key[key],
                answer_md=parsed.get("answer_md", ""),
                word_count=parsed.get("word_count", 0),
            )
        )

    return out
