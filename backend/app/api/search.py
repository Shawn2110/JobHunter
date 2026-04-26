from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.discovery.orchestrator import run_discovery
from app.discovery.types import SearchInput
from app.models import Job

router = APIRouter(tags=["search"])


class JobSourceOut(BaseModel):
    source_kind: str
    source_provider: str
    source_url: str


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    company_canonical: str
    location: str | None
    work_mode: str | None
    salary_text: str | None
    description_md: str | None
    posted_at: datetime | None
    apply_url: str | None
    ats_family: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    sources: list[JobSourceOut]


class SearchResponse(BaseModel):
    new_count: int
    updated_count: int
    jobs: list[JobOut]


@router.post("/search", response_model=SearchResponse)
async def search(
    payload: SearchInput,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    new_jobs, updated_jobs = await run_discovery(payload, session=session)
    # Refresh sources for serialization
    for j in [*new_jobs, *updated_jobs]:
        await session.refresh(j, attribute_names=["sources", "last_seen_at"])
    all_jobs = [*new_jobs, *updated_jobs]
    return {
        "new_count": len(new_jobs),
        "updated_count": len(updated_jobs),
        "jobs": all_jobs,
    }


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Job]:
    rows = (
        await session.execute(
            select(Job)
            .order_by(desc(Job.first_seen_at))
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Job | None:
    return await session.get(Job, job_id)
