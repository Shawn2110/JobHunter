from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.discovery.dedupe import canonical_company
from app.enrichment.linkedin_url import discover_linkedin_urls
from app.enrichment.signal import aggregate_company_signals
from app.models import Contact, Job

router = APIRouter(prefix="/contacts", tags=["contacts"])


class DiscoverContactsIn(BaseModel):
    job_id: int
    role_hints: list[str] | None = None
    company_about_url: str | None = None


class ContactOut(BaseModel):
    id: int
    company_canonical: str
    name: str | None
    role: str | None
    linkedin_url: str | None
    email: str | None
    email_source: str | None
    briefing_md: str | None
    signal_json: dict[str, Any] | None
    discovered_at: datetime
    last_refreshed_at: datetime | None


@router.post("/discover", response_model=list[ContactOut])
async def discover_contacts(
    payload: DiscoverContactsIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Contact]:
    job = await session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")

    cc = canonical_company(job.company)

    # 1. LinkedIn URL discovery (one query per role hint, deduped on URL)
    role_hints = payload.role_hints or [
        "engineering manager",
        "recruiter",
        "head of engineering",
        "head of talent",
    ]
    found: dict[str, Any] = {}  # url -> candidate
    for hint in role_hints:
        candidates = await discover_linkedin_urls(
            company=job.company,
            role_hint=hint,
            top_k=3,
        )
        for c in candidates:
            found.setdefault(c.linkedin_url, c)

    # 2. Public signal aggregation
    signal = await aggregate_company_signals(
        company=job.company,
        company_about_url=payload.company_about_url,
    )
    primary_email = signal.discovered_emails[0] if signal.discovered_emails else None

    # 3. Persist (upsert on company_canonical + linkedin_url)
    out: list[Contact] = []
    for url, cand in found.items():
        existing = (
            await session.execute(
                select(Contact).where(
                    Contact.company_canonical == cc,
                    Contact.linkedin_url == url,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            row = Contact(
                company_canonical=cc,
                name=cand.name,
                role=cand.role_hint,
                linkedin_url=url,
                email=primary_email[0] if primary_email else None,
                email_source=primary_email[1] if primary_email else None,
                briefing_md=signal.summary_md,
                signal_json={
                    "search_source": cand.source,
                    "discovered_emails": signal.discovered_emails,
                },
            )
            session.add(row)
        else:
            existing.briefing_md = signal.summary_md
            existing.signal_json = {
                "search_source": cand.source,
                "discovered_emails": signal.discovered_emails,
            }
            row = existing
        out.append(row)

    await session.commit()
    for r in out:
        await session.refresh(r)
    return out


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    session: Annotated[AsyncSession, Depends(get_session)],
    company_canonical: str | None = None,
) -> list[Contact]:
    stmt = select(Contact)
    if company_canonical:
        stmt = stmt.where(Contact.company_canonical == company_canonical)
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)
