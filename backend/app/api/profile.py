from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.prompt_loader import PromptError, PromptLoader
from app.db import get_session
from app.deps import get_claude, get_prompt_loader, resume_storage_dir
from app.models import Profile, ProfileHandle, Resume
from app.services.resume_parser import ResumeParseError, parse_resume

log = structlog.get_logger("app.api.profile")

router = APIRouter(prefix="/profile", tags=["profile"])


# ─── Pydantic schemas ────────────────────────────────────────────────────────


class ProfileHandleIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    username: str | None = None
    url: str = Field(min_length=1, max_length=512)


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    headline: str | None = None
    about_me_text: str | None = None
    target_seniority: str | None = None
    work_authorization: dict[str, Any] | None = None
    salary_floor: int | None = None
    salary_currency: str | None = Field(default=None, max_length=3)
    notice_period_days: int | None = None
    anti_preferences: dict[str, Any] | None = None
    handles: list[ProfileHandleIn] = Field(default_factory=list)


class ProfileHandleOut(BaseModel):
    id: int
    kind: str
    username: str | None
    url: str
    last_fetched_at: datetime | None


class ProfileOut(BaseModel):
    id: int
    name: str
    headline: str | None
    about_me_text: str | None
    target_seniority: str | None
    work_authorization: dict[str, Any] | None
    salary_floor: int | None
    salary_currency: str | None
    notice_period_days: int | None
    anti_preferences: dict[str, Any] | None
    handles: list[ProfileHandleOut]
    created_at: datetime
    updated_at: datetime


class ResumeOut(BaseModel):
    id: int
    version: int
    is_master: bool
    label: str | None
    parsed_json: dict[str, Any] | None
    source_file_path: str | None
    created_at: datetime


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.get("", response_model=ProfileOut | None)
async def get_profile(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Profile | None:
    result = await session.execute(select(Profile).limit(1))
    return result.scalar_one_or_none()


@router.put("", response_model=ProfileOut, status_code=status.HTTP_200_OK)
async def upsert_profile(
    payload: ProfileIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Profile:
    """Create or replace the single profile row.

    Single-user system: the first PUT creates the row; subsequent PUTs
    update it in place. Handles are replaced wholesale.
    """
    existing = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    fields = payload.model_dump(exclude={"handles"})

    if existing is None:
        profile = Profile(**fields)
        session.add(profile)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
        # Wipe and rebuild handles to keep the API simple.
        for h in list(existing.handles):
            await session.delete(h)
        profile = existing

    await session.flush()
    for h in payload.handles:
        session.add(ProfileHandle(profile_id=profile.id, **h.model_dump()))
    await session.commit()
    await session.refresh(profile, attribute_names=["handles"])
    return profile


@router.post(
    "/resume",
    response_model=ResumeOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: Annotated[UploadFile, File(description="PDF or DOCX resume")],
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> Resume:
    """Upload, store, and parse a resume.

    First upload becomes the master (`is_master=True`). Subsequent
    uploads create new master versions; tailored derivatives are
    handled in Phase 4.
    """
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file has no filename.",
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Persist to disk under data/resumes/
    storage = resume_storage_dir()
    suffix = "".join(c for c in file.filename if c.isalnum() or c in ".-_")[-80:]
    stored_name = f"{uuid.uuid4().hex}_{suffix or 'resume'}"
    stored_path = storage / stored_name
    stored_path.write_bytes(content)

    try:
        raw_text, parsed = await parse_resume(
            content=content,
            mime_type=file.content_type,
            filename=file.filename,
            claude=claude,
            loader=loader,
            session=session,
        )
    except ResumeParseError as e:
        # Clean up the stored file if parsing failed
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except PromptError as e:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"AI parser returned invalid output: {e}",
        ) from e

    # Determine version: max existing master version + 1, or 1 if first.
    existing_masters = (
        await session.execute(
            select(Resume).where(Resume.is_master.is_(True))
        )
    ).scalars().all()
    next_version = (
        max((r.version for r in existing_masters), default=0) + 1
    )

    resume = Resume(
        version=next_version,
        is_master=True,
        source_file_path=str(stored_path),
        source_mime_type=file.content_type,
        raw_text=raw_text,
        parsed_json=parsed,
        label=f"Master v{next_version}",
    )
    session.add(resume)
    await session.commit()
    await session.refresh(resume)

    log.info(
        "resume.uploaded",
        resume_id=resume.id,
        version=resume.version,
        chars=len(raw_text),
    )
    return resume
