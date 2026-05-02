from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.db import SessionLocal
from app.discovery.adapters.careers_page import CareersPageAdapter
from app.discovery.orchestrator import _merge
from app.discovery.types import SearchInput
from app.models import WatchlistCompany

log = structlog.get_logger("app.workers.nightly")


async def crawl_watchlist() -> int:
    """Crawl every WatchlistCompany.careers_url, merge results into the
    job index, update last_crawled / last_diff / last_new_count.

    Returns total new-job count across the run. Designed to be called
    from APScheduler at 03:00 local — but also runnable on demand
    from /admin/run-watchlist for manual testing.
    """
    adapter = CareersPageAdapter()
    total_new = 0

    async with SessionLocal() as session:
        rows = (
            await session.execute(select(WatchlistCompany))
        ).scalars().all()

        for row in rows:
            jobs = await adapter._fetch(  # noqa: SLF001 — internal use
                SearchInput(role="*", locations=[row.careers_url])
            )
            discovered = [(adapter, j) for j in jobs]
            new_jobs, updated = await _merge(discovered, session)

            row.last_crawled_at = datetime.now(timezone.utc)
            if new_jobs:
                row.last_diff_at = datetime.now(timezone.utc)
            row.last_new_count = len(new_jobs)
            total_new += len(new_jobs)
            log.info(
                "nightly.company_crawled",
                company=row.name,
                new=len(new_jobs),
                updated=len(updated),
            )

        await session.commit()

    log.info("nightly.complete", companies=len(rows), total_new=total_new)
    return total_new
