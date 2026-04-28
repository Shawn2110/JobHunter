from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.orchestrator import run_discovery
from app.discovery.types import SearchInput
from app.models import Job, SearchQuery

log = structlog.get_logger("app.services.diff")


@dataclass
class DiffResult:
    new_jobs: list[Job]          # first_seen_at > previous last_run_at
    updated_jobs: list[Job]      # already known but seen again this run
    ran_at: datetime
    previous_run_at: datetime | None


def search_query_to_input(query: SearchQuery) -> SearchInput:
    return SearchInput(
        role=query.role,
        domain=query.domain,
        locations=query.locations_json or [],
        work_mode=query.work_mode or "any",  # type: ignore[arg-type]
        salary_floor=query.salary_floor,
    )


async def run_saved_search(
    query: SearchQuery,
    session: AsyncSession,
) -> DiffResult:
    """Run discovery for a saved search and return a diff against the
    previous run.

    "New" = jobs whose `first_seen_at` is later than the previous
    `last_run_at`. The orchestrator already tracks first_seen vs.
    last_seen, so we only need a windowed query against `Job`.
    """
    previous = query.last_run_at
    ran_at = datetime.now(timezone.utc)

    await run_discovery(search_query_to_input(query), session=session)

    new_jobs: list[Job] = []
    updated_jobs: list[Job] = []
    if previous is not None:
        new_jobs = list(
            (
                await session.execute(
                    select(Job).where(Job.first_seen_at > previous)
                )
            )
            .scalars()
            .all()
        )
        updated_jobs = list(
            (
                await session.execute(
                    select(Job).where(
                        Job.first_seen_at <= previous,
                        Job.last_seen_at > previous,
                    )
                )
            )
            .scalars()
            .all()
        )
    else:
        # First run — every row is "new" relative to no prior baseline.
        new_jobs = list(
            (await session.execute(select(Job))).scalars().all()
        )

    query.last_run_at = ran_at
    await session.commit()

    log.info(
        "diff.saved_search_run",
        query_id=query.id,
        previous_run_at=previous.isoformat() if previous else None,
        new=len(new_jobs),
        updated=len(updated_jobs),
    )
    return DiffResult(
        new_jobs=new_jobs,
        updated_jobs=updated_jobs,
        ran_at=ran_at,
        previous_run_at=previous,
    )
