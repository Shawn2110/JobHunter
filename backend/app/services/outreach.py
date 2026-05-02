from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.models import Contact, Job, OutreachDraft, Profile

log = structlog.get_logger("app.services.outreach")

ALLOWED_INTENTS = {"referral", "application_support", "cold_intro"}


def _profile_payload(profile: Profile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "headline": profile.headline,
        "about_me_text": profile.about_me_text,
        "target_seniority": profile.target_seniority,
    }


def _contact_payload(contact: Contact) -> dict[str, Any]:
    return {
        "name": contact.name,
        "role": contact.role,
        "company_canonical": contact.company_canonical,
        "linkedin_url": contact.linkedin_url,
        "briefing_md": contact.briefing_md,
    }


def _job_payload(job: Job | None) -> dict[str, Any]:
    if job is None:
        return {}
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
    }


async def generate_outreach_brief(
    *,
    profile: Profile,
    contact: Contact,
    job: Job | None,
    intent: str,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
) -> OutreachDraft:
    if intent not in ALLOWED_INTENTS:
        raise ValueError(f"Unknown intent: {intent}")
    rendered = loader.render(
        "meta",
        "outreach_brief",
        {
            "profile": _profile_payload(profile),
            "contact": _contact_payload(contact),
            "job": _job_payload(job),
            "intent": intent,
        },
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )
    draft = OutreachDraft(
        contact_id=contact.id,
        job_id=job.id if job else None,
        intent=intent,
        brief_json=parsed,
    )
    session.add(draft)
    await session.commit()
    await session.refresh(draft)
    log.info("outreach.brief", draft_id=draft.id, intent=intent)
    return draft


async def execute_outreach(
    *,
    draft: OutreachDraft,
    profile: Profile,
    contact: Contact,
    job: Job | None,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession,
) -> OutreachDraft:
    effective_brief = draft.user_edits_json or draft.brief_json or {}
    rendered = loader.render(
        "execution",
        "outreach_draft",
        {
            "brief": effective_brief,
            "profile": _profile_payload(profile),
            "contact": _contact_payload(contact),
            "job": _job_payload(job),
            "intent": draft.intent,
        },
    )
    parsed, _ = await claude.complete_json(
        rendered, loader=loader, session=session
    )
    draft.draft_text = parsed.get("draft_text")
    draft.reasoning_text = parsed.get("reasoning_text")
    await session.commit()
    await session.refresh(draft)
    log.info("outreach.executed", draft_id=draft.id)
    return draft


async def humanize_pass(
    *,
    text: str,
    claude: ClaudeClient,
    loader: PromptLoader,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    rendered = loader.render("execution", "humanize", {"text": text})
    parsed, _ = await claude.complete_json(rendered, loader=loader, session=session)
    return parsed
