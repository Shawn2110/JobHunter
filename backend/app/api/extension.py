from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.discovery.dedupe import canonical_company
from app.models import Job, JobSource, Profile, Resume

router = APIRouter(prefix="/extension", tags=["extension"])


class SaveJobIn(BaseModel):
    """Accepts both the legacy URL+title shape and the v1.x rich shape.

    Either provide `url` (legacy minimal) or `apply_url` (rich,
    matches the content-script extractor's output schema). Other
    fields are optional and used when present.
    """

    # Rich shape (preferred)
    portal: str | None = None
    title: str | None = None
    company: str | None = None
    location: str | None = None
    description_md: str | None = None
    apply_url: str | None = None

    # Legacy minimal shape
    url: str | None = None


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
    """Save a job from the extension. Accepts both legacy and rich shapes.

    Rich shape (v1.x) carries portal name, full JD text, company,
    location — enough for fit + trust assessment to run later from
    the package page. Legacy shape (URL + title only) still works for
    pages where the content script didn't run.

    Dedup: if a Job with the same apply_url already exists, return
    that one with a new JobSource row instead of creating a duplicate.
    """
    apply_url = payload.apply_url or payload.url
    if not apply_url:
        return {"error": "apply_url or url is required"}

    title = payload.title or "Saved job"
    company = (payload.company or "").strip() or "(saved)"
    cc = canonical_company(company) if company != "(saved)" else "(saved)"

    # Look for an existing Job with the same apply_url
    existing = (
        await session.execute(select(Job).where(Job.apply_url == apply_url))
    ).scalar_one_or_none()

    if existing is not None:
        # Already saved — just record another sighting
        session.add(
            JobSource(
                job_id=existing.id,
                source_kind="careers_page",
                source_provider=f"extension_save_{payload.portal or 'manual'}",
                source_url=apply_url,
                seen_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        return {
            "id": existing.id,
            "title": existing.title,
            "apply_url": existing.apply_url,
            "duplicate": True,
        }

    job = Job(
        title=title,
        company=company,
        company_canonical=cc,
        location=payload.location,
        description_md=payload.description_md,
        apply_url=apply_url,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobSource(
            job_id=job.id,
            source_kind="careers_page",
            source_provider=f"extension_save_{payload.portal or 'manual'}",
            source_url=apply_url,
            seen_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()
    return {
        "id": job.id,
        "title": job.title,
        "apply_url": job.apply_url,
        "company": job.company,
        "has_description": bool(job.description_md),
    }
