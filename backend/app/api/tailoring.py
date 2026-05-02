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
from app.models import Job, Profile, Resume, TailoredArtifact, TailoringBrief
from app.services.resume_render import render_resume_markdown
from app.services.tailoring import (
    TailoringError,
    execute_tailoring,
    generate_brief,
)

router = APIRouter(prefix="/tailoring", tags=["tailoring"])


class BriefOut(BaseModel):
    id: int
    job_id: int
    base_resume_id: int
    brief_json: dict[str, Any]
    user_edits_json: dict[str, Any] | None
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime


class BriefEditsIn(BaseModel):
    user_edits_json: dict[str, Any]


class ArtifactOut(BaseModel):
    id: int
    brief_id: int
    kind: str
    content_json: dict[str, Any] | None
    content_md: str | None
    truthfulness_passed: bool | None
    truthfulness_violations_json: list[str] | None
    created_at: datetime


@router.post(
    "/jobs/{job_id}/brief",
    response_model=BriefOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_brief(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> TailoringBrief:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set up your profile before tailoring (PUT /profile).",
        )

    base_resume = (
        await session.execute(
            select(Resume)
            .where(Resume.is_master.is_(True))
            .order_by(desc(Resume.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    if base_resume is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload a master resume before tailoring (POST /profile/resume).",
        )

    brief = await generate_brief(
        job=job,
        profile=profile,
        base_resume=base_resume,
        claude=claude,
        loader=loader,
        session=session,
    )
    return brief


@router.put("/briefs/{brief_id}/edits", response_model=BriefOut)
async def edit_brief(
    brief_id: int,
    payload: BriefEditsIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TailoringBrief:
    brief = await session.get(TailoringBrief, brief_id)
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brief not found")
    brief.user_edits_json = payload.user_edits_json
    brief.approved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(brief)
    return brief


@router.post(
    "/briefs/{brief_id}/execute",
    response_model=ArtifactOut,
    status_code=status.HTTP_201_CREATED,
)
async def execute_brief(
    brief_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> TailoredArtifact:
    brief = await session.get(TailoringBrief, brief_id)
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brief not found")
    base_resume = await session.get(Resume, brief.base_resume_id)
    job = await session.get(Job, brief.job_id)
    if base_resume is None or job is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Base resume or job no longer exists.",
        )

    try:
        artifact = await execute_tailoring(
            brief=brief,
            base_resume=base_resume,
            job=job,
            claude=claude,
            loader=loader,
            session=session,
        )
    except TailoringError as e:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(e)
        ) from e

    if artifact.content_json:
        artifact.content_md = render_resume_markdown(artifact.content_json)
        await session.commit()
        await session.refresh(artifact)
    return artifact


@router.get("/briefs/{brief_id}", response_model=BriefOut)
async def get_brief(
    brief_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TailoringBrief:
    brief = await session.get(TailoringBrief, brief_id)
    if brief is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brief not found")
    return brief


@router.get("/briefs/{brief_id}/artifacts", response_model=list[ArtifactOut])
async def list_artifacts(
    brief_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TailoredArtifact]:
    rows = (
        await session.execute(
            select(TailoredArtifact)
            .where(TailoredArtifact.brief_id == brief_id)
            .order_by(desc(TailoredArtifact.created_at))
        )
    ).scalars().all()
    return list(rows)
