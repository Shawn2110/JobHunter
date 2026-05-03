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
from app.services.cover_letter import generate_cover_letter
from app.services.custom_questions import (
    COMMON_QUESTIONS,
    generate_custom_answers,
)
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
    kind: str
    brief_json: dict[str, Any]
    user_edits_json: dict[str, Any] | None
    approved_at: datetime | None
    executed_at: datetime | None
    created_at: datetime


class BriefEditsIn(BaseModel):
    user_edits_json: dict[str, Any]


class ArtifactOut(BaseModel):
    id: int
    job_id: int
    brief_id: int | None
    kind: str
    content_json: dict[str, Any] | None
    content_md: str | None
    truthfulness_passed: bool | None
    truthfulness_violations_json: list[str] | None
    created_at: datetime


class CoverLetterOut(BaseModel):
    brief: BriefOut
    artifact: ArtifactOut


class CustomQuestionsIn(BaseModel):
    keys: list[str] | None = None  # None → all 5 default questions


class CustomAnswerOut(BaseModel):
    key: str
    question: str
    answer_md: str
    word_count: int


class CustomQuestionsOut(BaseModel):
    artifact_id: int
    answers: list[CustomAnswerOut]


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


# ─── Cover letter ───────────────────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/cover-letter",
    response_model=CoverLetterOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_cover_letter(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> dict[str, Any]:
    """One-shot cover-letter generation for a job.

    Runs Layer-1 brief → Layer-2 execution inline. Persists both the
    brief (kind='cover_letter') and the artifact. Returns both so the
    UI can show the strategy alongside the letter.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set up your profile before generating a cover letter (PUT /profile).",
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
            "Upload a master resume before generating a cover letter.",
        )

    brief, artifact = await generate_cover_letter(
        job=job,
        profile=profile,
        base_resume=base_resume,
        claude=claude,
        loader=loader,
        session=session,
    )
    return {"brief": brief, "artifact": artifact}


# ─── Custom-question answers ────────────────────────────────────────────────


@router.post(
    "/jobs/{job_id}/custom-questions",
    response_model=CustomQuestionsOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_custom_answers(
    job_id: int,
    payload: CustomQuestionsIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> dict[str, Any]:
    """Pre-generate answers for the standard ATS custom questions.

    Persists ONE TailoredArtifact (kind='custom_answers') with all
    answers in content_json. No brief — each question runs as a
    standalone static prompt.
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Set up your profile before generating custom answers.",
        )

    base_resume = (
        await session.execute(
            select(Resume)
            .where(Resume.is_master.is_(True))
            .order_by(desc(Resume.version))
            .limit(1)
        )
    ).scalar_one_or_none()
    resume_json = (base_resume.parsed_json if base_resume else {}) or {}

    profile_payload = {
        "name": profile.name,
        "headline": profile.headline,
        "about_me_text": profile.about_me_text,
        "target_seniority": profile.target_seniority,
        "salary_floor": profile.salary_floor,
        "salary_currency": profile.salary_currency,
        "notice_period_days": profile.notice_period_days,
    }
    job_payload = {
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description_md": job.description_md,
        "salary_text": job.salary_text,
    }

    answers = await generate_custom_answers(
        profile_payload=profile_payload,
        resume_json=resume_json,
        job_payload=job_payload,
        keys=payload.keys,
        claude=claude,
        loader=loader,
        session=session,
    )

    # Persist as one bundled artifact
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
    await session.refresh(artifact)

    return {
        "artifact_id": artifact.id,
        "answers": [
            {
                "key": a.key,
                "question": a.question,
                "answer_md": a.answer_md,
                "word_count": a.word_count,
            }
            for a in answers
        ],
    }


# ─── Convenience: list all artifacts for a job (any kind, any brief) ────────


@router.get("/jobs/{job_id}/artifacts", response_model=list[ArtifactOut])
async def list_job_artifacts(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[TailoredArtifact]:
    rows = (
        await session.execute(
            select(TailoredArtifact)
            .where(TailoredArtifact.job_id == job_id)
            .order_by(desc(TailoredArtifact.created_at))
        )
    ).scalars().all()
    return list(rows)
