from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_scheduler_registers_nightly_job() -> None:
    """Light smoke test: scheduler constructs, registers the cron job,
    and shuts down without firing it. AsyncIOScheduler needs a running
    loop, hence the async test."""
    from app.workers.scheduler import shutdown_scheduler, start_scheduler

    sched = start_scheduler()
    try:
        jobs = {j.id for j in sched.get_jobs()}
        assert "nightly_watchlist" in jobs
        # Idempotent: calling again returns the same instance.
        again = start_scheduler()
        assert again is sched
    finally:
        shutdown_scheduler()
