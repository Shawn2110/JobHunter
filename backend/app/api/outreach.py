from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptLoader
from app.db import get_session
from app.deps import get_claude, get_prompt_loader
from app.models import Contact, Job, OutreachDraft, Profile
from app.services.outreach import (
    ALLOWED_INTENTS,
    execute_outreach,
    generate_outreach_brief,
    humanize_pass,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])


class CreateBriefIn(BaseModel):
    contact_id: int
    job_id: int | None = None
    intent: str  # referral | application_support | cold_intro


class EditBriefIn(BaseModel):
    user_edits_json: dict[str, Any]


class HumanizeIn(BaseModel):
    text: str


class DraftOut(BaseModel):
    id: int
    contact_id: int
    job_id: int | None
    intent: str
    brief_json: dict[str, Any] | None
    user_edits_json: dict[str, Any] | None
    draft_text: str | None
    reasoning_text: str | None
    created_at: datetime
    sent_manually_at: datetime | None


@router.post(
    "/briefs",
    response_model=DraftOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_brief(
    payload: CreateBriefIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> OutreachDraft:
    if payload.intent not in ALLOWED_INTENTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"intent must be one of {sorted(ALLOWED_INTENTS)}",
        )
    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Profile not set up")
    contact = await session.get(Contact, payload.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    job = await session.get(Job, payload.job_id) if payload.job_id else None
    return await generate_outreach_brief(
        profile=profile,
        contact=contact,
        job=job,
        intent=payload.intent,
        claude=claude,
        loader=loader,
        session=session,
    )


@router.put("/drafts/{draft_id}/edits", response_model=DraftOut)
async def edit_brief(
    draft_id: int,
    payload: EditBriefIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OutreachDraft:
    draft = await session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    draft.user_edits_json = payload.user_edits_json
    await session.commit()
    await session.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/execute", response_model=DraftOut)
async def execute_draft(
    draft_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> OutreachDraft:
    draft = await session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    contact = await session.get(Contact, draft.contact_id)
    job = await session.get(Job, draft.job_id) if draft.job_id else None
    if profile is None or contact is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Profile or contact no longer exists"
        )
    return await execute_outreach(
        draft=draft,
        profile=profile,
        contact=contact,
        job=job,
        claude=claude,
        loader=loader,
        session=session,
    )


@router.post("/humanize")
async def humanize(
    payload: HumanizeIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> dict[str, Any]:
    return await humanize_pass(
        text=payload.text, claude=claude, loader=loader, session=session
    )


@router.post("/drafts/{draft_id}/mark-sent", response_model=DraftOut)
async def mark_sent(
    draft_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> OutreachDraft:
    draft = await session.get(OutreachDraft, draft_id)
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    draft.sent_manually_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(draft)
    return draft


@router.get("/contacts/{contact_id}/drafts", response_model=list[DraftOut])
async def list_drafts(
    contact_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[OutreachDraft]:
    rows = (
        await session.execute(
            select(OutreachDraft)
            .where(OutreachDraft.contact_id == contact_id)
            .order_by(desc(OutreachDraft.created_at))
        )
    ).scalars().all()
    return list(rows)
