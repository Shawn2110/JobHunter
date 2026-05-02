from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.discovery.adapters.adzuna import AdzunaAdapter
from app.discovery.adapters.base import DiscoveryAdapter
from app.discovery.adapters.careers_page import CareersPageAdapter
from app.discovery.adapters.jooble import JoobleAdapter
from app.discovery.adapters.jsearch import JSearchAdapter
from app.discovery.adapters.reddit import RedditAdapter
from app.discovery.ats import detect_ats_family
from app.discovery.dedupe import (
    canonical_company,
    is_duplicate,
    normalize_title,
)
from app.discovery.types import DiscoveredJob, SearchInput
from app.models import Job, JobSource

log = structlog.get_logger("app.discovery.orchestrator")


def default_aggregator_adapters() -> list[DiscoveryAdapter]:
    """All Mode-1 adapters; each self-skips if not configured."""
    return [JSearchAdapter(), AdzunaAdapter(), JoobleAdapter()]


def default_founder_post_adapters() -> list[DiscoveryAdapter]:
    """Mode-2 adapters. Reddit is the only one viable without paid
    Twitter / Wellfound API access in v1; rest land as follow-ups."""
    return [RedditAdapter()]


def default_careers_page_adapters() -> list[DiscoveryAdapter]:
    """Mode-3 adapter. Single adapter that crawls each user-supplied
    URL with per-domain rate limiting."""
    return [CareersPageAdapter()]


def adapters_for_modes(modes: list[str] | None) -> list[DiscoveryAdapter]:
    """Resolve mode names to adapter instances.

    Modes default to ['aggregator']. Pass any combination of
    'aggregator' | 'founder_post' | 'careers_page'.
    """
    modes = modes or ["aggregator"]
    out: list[DiscoveryAdapter] = []
    if "aggregator" in modes:
        out.extend(default_aggregator_adapters())
    if "founder_post" in modes:
        out.extend(default_founder_post_adapters())
    if "careers_page" in modes:
        out.extend(default_careers_page_adapters())
    return out


async def run_discovery(
    query: SearchInput,
    session: AsyncSession,
    adapters: Sequence[DiscoveryAdapter] | None = None,
) -> tuple[list[Job], list[Job]]:
    """Run discovery across enabled adapters and persist results.

    Returns `(new_jobs, updated_jobs)`:
    - new_jobs: rows that were inserted
    - updated_jobs: rows that already existed and gained a new
      JobSource (or had last_seen_at bumped)
    """
    adapters = adapters or default_aggregator_adapters()
    enabled = [a for a in adapters if a.is_configured()]
    log.info(
        "discovery.start",
        adapters=[a.name for a in enabled],
        skipped=[a.name for a in adapters if not a.is_configured()],
    )

    if not enabled:
        return [], []

    results = await asyncio.gather(
        *[a.discover(query) for a in enabled], return_exceptions=False
    )

    discovered: list[tuple[DiscoveryAdapter, DiscoveredJob]] = []
    for adapter, batch in zip(enabled, results, strict=True):
        for job in batch:
            discovered.append((adapter, job))

    log.info("discovery.discovered", total=len(discovered))

    new_jobs, updated_jobs = await _merge(discovered, session)
    log.info(
        "discovery.merged",
        new=len(new_jobs),
        updated=len(updated_jobs),
    )
    return new_jobs, updated_jobs


async def _merge(
    discovered: list[tuple[DiscoveryAdapter, DiscoveredJob]],
    session: AsyncSession,
) -> tuple[list[Job], list[Job]]:
    """Persist discovered jobs into Job/JobSource, deduplicating in two passes:

    1. Within the batch — same canonical company + title coalesces.
    2. Against the DB — match against existing rows where company_canonical
       + normalized title overlap, then check description similarity.
    """
    # Pass 1: coalesce within the batch
    batch_buckets: dict[tuple[str, str], list[tuple[DiscoveryAdapter, DiscoveredJob]]] = {}
    for adapter, job in discovered:
        key = (canonical_company(job.company), normalize_title(job.title))
        batch_buckets.setdefault(key, []).append((adapter, job))

    new_jobs: list[Job] = []
    updated_jobs: list[Job] = []
    now = datetime.now(timezone.utc)

    for (cc, _nt), group in batch_buckets.items():
        # Use the first job in the group as the canonical record
        primary_adapter, primary = group[0]

        # Pass 2: check against existing DB rows for this canonical company
        existing_rows = (
            await session.execute(
                select(Job).where(Job.company_canonical == cc)
            )
        ).scalars().all()

        match: Job | None = None
        for row in existing_rows:
            if is_duplicate(
                row.company,
                row.title,
                row.description_md,
                primary.company,
                primary.title,
                primary.description_md,
            ):
                match = row
                break

        if match is None:
            # Insert a new Job
            new_job = Job(
                title=primary.title,
                company=primary.company,
                company_canonical=cc,
                location=primary.location,
                work_mode=primary.work_mode,
                salary_text=primary.salary_text,
                description_md=primary.description_md,
                posted_at=primary.posted_at,
                apply_url=primary.apply_url,
                ats_family=detect_ats_family(primary.apply_url),
            )
            session.add(new_job)
            await session.flush()
            for adapter, job in group:
                session.add(
                    JobSource(
                        job_id=new_job.id,
                        source_kind=adapter.source_kind,
                        source_provider=adapter.name,
                        source_url=job.apply_url or "",
                    )
                )
            new_jobs.append(new_job)
        else:
            # Update last_seen and add any new sources we don't already have
            match.last_seen_at = now
            existing_provider_urls = {
                (s.source_provider, s.source_url) for s in match.sources
            }
            for adapter, job in group:
                key = (adapter.name, job.apply_url or "")
                if key not in existing_provider_urls:
                    session.add(
                        JobSource(
                            job_id=match.id,
                            source_kind=adapter.source_kind,
                            source_provider=adapter.name,
                            source_url=job.apply_url or "",
                        )
                    )
            updated_jobs.append(match)

    await session.commit()
    return new_jobs, updated_jobs
