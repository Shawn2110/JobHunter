from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.discovery.orchestrator import run_discovery
from app.discovery.types import SearchInput
from app.models import Job, SearchQuery
from app.services.diff import run_saved_search

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


# ─── Saved searches (diff feed) ─────────────────────────────────────────────


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=255)
    domain: str | None = None
    locations: list[str] = Field(default_factory=list)
    work_mode: str | None = "any"
    salary_floor: int | None = None
    modes_enabled: list[str] = Field(default_factory=lambda: ["aggregator"])


class SavedSearchOut(BaseModel):
    id: int
    name: str
    role: str
    domain: str | None
    locations_json: list[str] | None
    work_mode: str | None
    salary_floor: int | None
    modes_enabled_json: list[str] | None
    last_run_at: datetime | None
    created_at: datetime


class DiffOut(BaseModel):
    ran_at: datetime
    previous_run_at: datetime | None
    new_jobs: list[JobOut]
    updated_jobs: list[JobOut]


@router.post("/search/saved", response_model=SavedSearchOut, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    payload: SavedSearchIn,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SearchQuery:
    sq = SearchQuery(
        name=payload.name,
        role=payload.role,
        domain=payload.domain,
        locations_json=payload.locations,
        work_mode=payload.work_mode,
        salary_floor=payload.salary_floor,
        modes_enabled_json=payload.modes_enabled,
    )
    session.add(sq)
    await session.commit()
    await session.refresh(sq)
    return sq


@router.get("/search/saved", response_model=list[SavedSearchOut])
async def list_saved_searches(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[SearchQuery]:
    rows = (
        await session.execute(
            select(SearchQuery).order_by(desc(SearchQuery.created_at))
        )
    ).scalars().all()
    return list(rows)


@router.post("/search/saved/{query_id}/run", response_model=DiffOut)
async def run_saved(
    query_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    sq = await session.get(SearchQuery, query_id)
    if sq is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found",
        )
    result = await run_saved_search(sq, session)
    for j in [*result.new_jobs, *result.updated_jobs]:
        await session.refresh(j, attribute_names=["sources", "last_seen_at"])
    return {
        "ran_at": result.ran_at,
        "previous_run_at": result.previous_run_at,
        "new_jobs": result.new_jobs,
        "updated_jobs": result.updated_jobs,
    }
