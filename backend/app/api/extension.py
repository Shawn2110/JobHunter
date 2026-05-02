from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Job, JobSource, Profile, Resume

router = APIRouter(prefix="/extension", tags=["extension"])


class SaveJobIn(BaseModel):
    url: str
    title: str | None = None


class ApplicationPackageOut(BaseModel):
    profile: dict[str, Any] | None
    resume_summary: dict[str, Any] | None


@router.get("/application-package", response_model=ApplicationPackageOut)
async def application_package(
    session: Annotated[AsyncSession, Depends(get_session)],
    url: str | None = None,
) -> dict[str, Any]:
    """Return the bundle the autofill content script needs.

    Profile (name, contact, links) + a resume summary. We never return
    the full parsed resume — autofill should only need name/contact/
    short summary fields.
    """
    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    resume = (
        await session.execute(
            select(Resume)
            .where(Resume.is_master.is_(True))
            .order_by(Resume.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    profile_payload: dict[str, Any] | None = None
    if profile:
        # Pull email/phone/links off the parsed resume since profile
        # itself doesn't store them.
        parsed = (resume.parsed_json if resume else {}) or {}
        profile_payload = {
            "name": profile.name,
            "email": parsed.get("email"),
            "phone": parsed.get("phone"),
            "links": parsed.get("links") or [],
        }

    resume_summary: dict[str, Any] | None = None
    if resume and resume.parsed_json:
        rj = resume.parsed_json
        resume_summary = {
            "summary": rj.get("summary"),
            "skills": rj.get("skills") or [],
        }

    return {"profile": profile_payload, "resume_summary": resume_summary}


@router.post("/save-job")
async def save_job(
    payload: SaveJobIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Quick-save a careers-page URL the user found in the wild.

    Inserts a minimal Job + JobSource(careers_page). The full crawl /
    parse comes later when Phase 8 wires up Mode 3 properly.
    """
    title = payload.title or "Saved job"
    job = Job(
        title=title,
        company="(saved)",
        company_canonical="(saved)",
        apply_url=payload.url,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobSource(
            job_id=job.id,
            source_kind="careers_page",
            source_provider="extension_save",
            source_url=payload.url,
            seen_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    return {"id": job.id, "title": job.title, "apply_url": job.apply_url}
