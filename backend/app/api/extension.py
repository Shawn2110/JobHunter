from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.claude import ClaudeClient
from app.ai.fit import compute_fit_dict, load_handle_signals, profile_payload
from app.ai.knockouts import extract_knockouts
from app.ai.prompt_loader import PromptLoader
from app.db import get_session
from app.deps import get_claude, get_prompt_loader
from app.discovery.dedupe import canonical_company
from app.models import Job, JobSource, Profile, Resume
from app.trust.service import compute_trust_dict
from app.workers.background_tailor import tailor_job_in_background

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
        # Pull contact + current-employment off the parsed resume since
        # Profile itself doesn't store them. current_title / current_company
        # come from experience[0] (the resume parser orders most-recent
        # first) and let the autofill bar populate "Current employer" /
        # "Current title" fields on application forms.
        parsed = (resume.parsed_json if resume else {}) or {}
        experience = parsed.get("experience") or []
        current = experience[0] if experience and isinstance(experience[0], dict) else {}
        profile_payload = {
            "name": profile.name,
            "email": parsed.get("email"),
            "phone": parsed.get("phone"),
            "location": parsed.get("location"),
            "links": parsed.get("links") or [],
            "current_title": current.get("title"),
            "current_company": current.get("company"),
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


# ─── Live preview scoring (v2 — extension overlay) ──────────────────────────


class ScoreIn(BaseModel):
    """Same shape the content script extracts. apply_url is required
    so we can dedup if the user later saves; everything else is
    optional but stronger results follow when provided."""

    portal: str | None = None
    title: str
    company: str
    location: str | None = None
    description_md: str | None = None
    apply_url: str
    locale: str = "global"


class ScoreOut(BaseModel):
    fit: dict[str, Any] | None
    trust: dict[str, Any] | None
    knockouts: list[dict[str, Any]]
    has_profile: bool
    has_resume: bool
    notes: list[str]


@router.post("/score", response_model=ScoreOut)
async def live_score(
    payload: ScoreIn,
    session: Annotated[AsyncSession, Depends(get_session)],
    claude: Annotated[ClaudeClient, Depends(get_claude)],
    loader: Annotated[PromptLoader, Depends(get_prompt_loader)],
) -> dict[str, Any]:
    """Live in-page preview: fit + trust + knockouts on a JD, no
    persistence. Used by the extension overlay while the user is
    browsing.

    Returns partial results when profile or resume isn't set up — fit
    needs both, trust + knockouts need only the JD. The `notes` array
    surfaces these gracefully so the overlay can prompt the user to
    finish setup.
    """
    notes: list[str] = []

    profile = (
        await session.execute(select(Profile).limit(1))
    ).scalar_one_or_none()
    resume = (
        await session.execute(
            select(Resume)
            .where(Resume.is_master.is_(True))
            .order_by(desc(Resume.version))
            .limit(1)
        )
    ).scalar_one_or_none()

    has_profile = profile is not None
    has_resume = resume is not None

    # ── Knockouts (always available — no profile/resume needed) ──
    knockouts = await extract_knockouts(
        job_title=payload.title,
        job_description=payload.description_md or "",
        claude=claude,
        loader=loader,
        session=None,
    )

    # ── Trust (always available — no profile/resume needed) ──
    trust = await compute_trust_dict(
        job_title=payload.title,
        company=payload.company,
        description_md=payload.description_md,
        apply_url=payload.apply_url,
        claude=claude,
        loader=loader,
        session=None,
        locale=payload.locale,  # type: ignore[arg-type]
    )

    # ── Fit (requires profile + resume) ──
    fit: dict[str, Any] | None = None
    if not has_profile:
        notes.append("Set up your profile to enable fit scoring.")
    elif not has_resume:
        notes.append("Upload a master resume to enable fit scoring.")
    else:
        handle_signals = await load_handle_signals(session, profile.id)  # type: ignore[arg-type]
        fit = await compute_fit_dict(
            profile_payload=profile_payload(profile),  # type: ignore[arg-type]
            resume_json=resume.parsed_json or {},  # type: ignore[union-attr]
            handle_signals=handle_signals,
            job_payload={
                "title": payload.title,
                "company": payload.company,
                "location": payload.location,
                "description_md": payload.description_md,
                "ats_family": None,
            },
            claude=claude,
            loader=loader,
            session=None,
        )

    return {
        "fit": fit,
        "trust": trust,
        "knockouts": knockouts,
        "has_profile": has_profile,
        "has_resume": has_resume,
        "notes": notes,
    }


# ─── Save + kick off tailoring in the background (v2 — overlay action) ──────


class SaveAndTailorIn(ScoreIn):
    """Same shape as ScoreIn — payload comes from the same content-script
    extractor."""


class SaveAndTailorOut(BaseModel):
    job_id: int
    package_url: str
    duplicate: bool
    tailoring_status: str  # "kicked_off" | "skipped_no_profile" | "skipped_no_resume"


@router.post("/save-and-tailor", response_model=SaveAndTailorOut)
async def save_and_tailor(
    payload: SaveAndTailorIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """Persist Job + JobSource, return immediately with a deep-link
    to the package page where the user can trigger / view the
    tailoring artifacts.

    Doesn't actually run tailoring inline — that's a 30-60 second
    operation we don't want to block the extension UI on. The package
    page handles generation on first open. (Future v2.x: background
    job that pre-generates so the package is ready when the user
    clicks through.)
    """
    company = (payload.company or "").strip() or "(saved)"
    cc = canonical_company(company) if company != "(saved)" else "(saved)"

    existing = (
        await session.execute(select(Job).where(Job.apply_url == payload.apply_url))
    ).scalar_one_or_none()

    if existing is not None:
        session.add(
            JobSource(
                job_id=existing.id,
                source_kind="careers_page",
                source_provider=f"extension_save_{payload.portal or 'manual'}",
                source_url=payload.apply_url,
                seen_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
        # Don't re-fire tailoring on duplicates — the artifacts (or
        # in-flight task from the first save) already exist. User can
        # regenerate from the package page if they want.
        return {
            "job_id": existing.id,
            "package_url": f"http://localhost:3000/jobs/{existing.id}/package",
            "duplicate": True,
            "tailoring_status": "skipped_duplicate",
        }

    job = Job(
        title=payload.title,
        company=company,
        company_canonical=cc,
        location=payload.location,
        description_md=payload.description_md,
        apply_url=payload.apply_url,
    )
    session.add(job)
    await session.flush()
    session.add(
        JobSource(
            job_id=job.id,
            source_kind="careers_page",
            source_provider=f"extension_save_{payload.portal or 'manual'}",
            source_url=payload.apply_url,
            seen_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()

    # Tailoring readiness check — surface in the response so the
    # extension can warn the user before they click through. When all
    # prereqs are present, kick off background tailoring so the
    # package page loads with everything ready.
    profile = (await session.execute(select(Profile).limit(1))).scalar_one_or_none()
    resume = (
        await session.execute(
            select(Resume).where(Resume.is_master.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if profile is None:
        status_str = "skipped_no_profile"
    elif resume is None:
        status_str = "skipped_no_resume"
    elif not settings_anthropic_key_configured():
        status_str = "skipped_no_anthropic_key"
    else:
        # Fire-and-forget. The task opens its own SessionLocal — the
        # request session has already closed by the time it runs. We
        # explicitly don't await this; the response returns immediately
        # so the extension overlay can show 'Open package' without a
        # 60-second wait.
        asyncio.create_task(tailor_job_in_background(job.id))
        status_str = "kicked_off"

    return {
        "job_id": job.id,
        "package_url": f"http://localhost:3000/jobs/{job.id}/package?gen=1",
        "duplicate": False,
        "tailoring_status": status_str,
    }


def settings_anthropic_key_configured() -> bool:
    """Module-level check so we don't have to import settings inline
    in the endpoint body."""
    from app.config import settings
    return bool(settings.anthropic_api_key)
